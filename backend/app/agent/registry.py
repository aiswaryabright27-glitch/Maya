"""Tool registry: schema-validated, permission-checked, never throws raw errors."""
from __future__ import annotations

import asyncio
import inspect
import json
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from .permissions import Decision, Level, PermissionEngine

Handler = Callable[[dict[str, Any]], Awaitable[dict[str, Any]] | dict[str, Any]]

_TYPES = {"string": str, "integer": int, "number": (int, float), "boolean": bool,
          "object": dict, "array": list}


def validate_args(schema: dict[str, Any], args: dict[str, Any]) -> list[str]:
    """Minimal JSON-schema check: required keys + primitive types. Returns errors."""
    errors: list[str] = []
    props = schema.get("properties", {})
    for key in schema.get("required", []):
        if key not in args:
            errors.append(f"missing required argument '{key}'")
    for key, value in args.items():
        spec = props.get(key)
        if spec is None:
            errors.append(f"unexpected argument '{key}'")
            continue
        expected = spec.get("type")
        if expected in _TYPES and not isinstance(value, _TYPES[expected]):
            # bool is subclass of int; exclude it from integer/number
            if expected in {"integer", "number"} and isinstance(value, bool):
                errors.append(f"argument '{key}' must be {expected}")
            elif expected != "integer" or not isinstance(value, int):
                errors.append(f"argument '{key}' must be {expected}")
    return errors


@dataclass
class ToolResult:
    ok: bool
    output: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    duration_ms: float = 0.0
    evidence: str | None = None


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict[str, Any]
    handler: Handler
    level: Level = Level.READ_ONLY
    risk_class: str = "safe"
    timeout: float = 30.0
    dry_run: bool = False


class ToolRegistry:
    def __init__(self, permissions: PermissionEngine, audit=None) -> None:
        self._tools: dict[str, Tool] = {}
        self.permissions = permissions
        self.audit = audit

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def list_tools(self) -> list[dict[str, Any]]:
        return [{"name": t.name, "description": t.description, "parameters": t.parameters,
                 "level": t.level.name, "risk": t.risk_class} for t in self._tools.values()]

    async def execute(self, name: str, args: dict[str, Any], *,
                      task_id: str | None = None, provenance: str | None = None,
                      dry_run: bool = False, confirmed: bool = False) -> ToolResult:
        tool = self._tools.get(name)
        if tool is None:
            return ToolResult(False, error=f"unknown tool '{name}'")
        decision = self.permissions.check(name, tool.level, tool.risk_class)
        if not decision.allowed:
            self._audit(name, args, f"denied:{decision.reason}", task_id, provenance)
            return ToolResult(False, error=decision.reason)
        if decision.needs_confirmation and not confirmed and not dry_run:
            self._audit(name, args, "confirmation_required", task_id, provenance)
            return ToolResult(False, error=f"confirmation required for {name}",
                              output={"needs_confirmation": True})
        errors = validate_args(tool.parameters, args)
        if errors:
            self._audit(name, args, f"invalid_args:{'; '.join(errors)}", task_id, provenance)
            return ToolResult(False, error="; ".join(errors))
        if dry_run or tool.dry_run:
            self._audit(name, args, "dry_run", task_id, provenance)
            return ToolResult(True, output={"dry_run": True, "tool": name, "args": args},
                              evidence="validated only; nothing executed")
        start = time.perf_counter()
        try:
            # Run the handler exactly ONCE, off the event loop. (The old code called the
            # handler directly and then again in a thread, so every tool ran twice.)
            result = await asyncio.wait_for(asyncio.to_thread(_call_sync, tool.handler, args), timeout=tool.timeout)
            if inspect.isawaitable(result):
                result = await asyncio.wait_for(result, timeout=tool.timeout)
            if not isinstance(result, dict):
                result = {"value": result}
            elapsed = (time.perf_counter() - start) * 1000
            if result.get("ok") is False:
                # A tool that returns {"ok": False, "error": ...} has FAILED; never report it as success.
                self._audit(name, args, "failed", task_id, provenance, result=json.dumps(result, ensure_ascii=False)[:300])
                return ToolResult(False, output=result, error=str(result.get("error") or f"{name} did not succeed"),
                                  duration_ms=elapsed, evidence=result.get("evidence"))
            self._audit(name, args, "ok", task_id, provenance, result=json.dumps(result, ensure_ascii=False)[:300])
            return ToolResult(True, output=result, duration_ms=elapsed,
                              evidence=result.get("evidence"))
        except asyncio.TimeoutError:
            self._audit(name, args, "timeout", task_id, provenance)
            return ToolResult(False, error=f"tool '{name}' timed out after {tool.timeout}s")
        except Exception as exc:  # tools must not leak raw exceptions to callers/LLM
            self._audit(name, args, f"error:{type(exc).__name__}", task_id, provenance)
            return ToolResult(False, error=f"{name} failed: {type(exc).__name__}")

    def _audit(self, name: str, args: dict[str, Any], decision: str,
               task_id: str | None, provenance: str | None, result: str | None = None) -> None:
        if self.audit is not None:
            try:
                self.audit.record(name, args, decision, result=result, task_id=task_id, provenance=provenance)
            except Exception:
                pass  # auditing must never break execution


def _call_sync(handler: Handler, args: dict[str, Any]) -> Any:
    return handler(args)
