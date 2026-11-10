"""Agent executor: runs routed commands/tools with budgets, cancellation, audit."""
from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable

from .registry import ToolRegistry
from .router import RoutedCommand

MAX_STEPS = 15
STEP_TIMEOUT = 30.0
TASK_BUDGET_S = 120.0


@dataclass
class StepRecord:
    index: int
    tool: str
    summary: str
    ok: bool
    detail: str
    duration_ms: float


@dataclass
class TaskResult:
    task_id: str
    status: str                     # completed | partial | failed | cancelled | needs_confirmation
    report: str
    steps: list[StepRecord] = field(default_factory=list)
    needs_confirmation: dict | None = None


class AgentExecutor:
    def __init__(self, registry: ToolRegistry, on_event: Callable[[dict], None] | None = None) -> None:
        self.registry = registry
        self.on_event = on_event or (lambda event: None)
        self._cancel: dict[str, asyncio.Event] = {}

    def cancel(self, task_id: str) -> None:
        event = self._cancel.get(task_id)
        if event:
            event.set()

    async def run_command(self, command: RoutedCommand, *,
                          provenance: str = "voice",
                          confirmed: bool = False) -> TaskResult:
        """Execute a single routed tool command end to end."""
        task_id = f"task_{uuid.uuid4().hex[:10]}"
        cancel_event = asyncio.Event()
        self._cancel[task_id] = cancel_event
        started = time.perf_counter()
        try:
            if command.kind == "stop":
                return TaskResult(task_id, "completed", "Stopped.", [])
            if command.kind in {"conversation", "task"} or not command.tool:
                return TaskResult(task_id, "completed",
                                  "I can help with that once the planner is enabled; for now try a direct command like 'open notepad' or 'search the web for news'.",
                                  [])
            self._emit(task_id, "tool_start", command.tool, command.summary)
            result = await self.registry.execute(
                command.tool, command.args, task_id=task_id,
                provenance=provenance, confirmed=confirmed)
            step = StepRecord(1, command.tool, command.summary, result.ok,
                              result.error or "ok", result.duration_ms)
            if result.output.get("needs_confirmation"):
                self._emit(task_id, "confirmation_required", command.tool, command.summary)
                return TaskResult(task_id, "needs_confirmation",
                                  f"I need your confirmation before running {command.tool}.",
                                  [step], needs_confirmation={"tool": command.tool, "args": command.args})
            status = "completed" if result.ok else "failed"
            report = result.output.get("report") or (
                f"Done: {command.summary}." if result.ok else f"Sorry, {result.error}.")
            self._emit(task_id, "tool_complete", command.tool, report)
            return TaskResult(task_id, status, report, [step])
        finally:
            self._cancel.pop(task_id, None)
            _ = time.perf_counter() - started

    async def run_plan(self, steps: list[dict[str, Any]], *,
                       provenance: str = "voice") -> TaskResult:
        """Execute a multi-step plan with budget, timeout and cancellation."""
        task_id = f"task_{uuid.uuid4().hex[:10]}"
        cancel_event = asyncio.Event()
        self._cancel[task_id] = cancel_event
        records: list[StepRecord] = []
        deadline = time.perf_counter() + TASK_BUDGET_S
        try:
            for i, step in enumerate(steps[:MAX_STEPS], start=1):
                if cancel_event.is_set() or time.perf_counter() > deadline:
                    return TaskResult(task_id, "cancelled",
                                      "Task stopped before finishing.", records)
                tool_name = step.get("tool", "")
                summary = step.get("summary", tool_name)
                self._emit(task_id, "tool_start", tool_name, summary, i, len(steps))
                result = await self.registry.execute(
                    tool_name, step.get("args", {}), task_id=task_id, provenance=provenance)
                ok = result.ok
                records.append(StepRecord(i, tool_name, summary, ok,
                                          result.error or "ok", result.duration_ms))
                self._emit(task_id, "tool_step", tool_name,
                           f"Step {i}/{len(steps)} {'done' if ok else 'failed'}", i, len(steps))
                if not ok:
                    return TaskResult(task_id, "partial" if records[:-1] else "failed",
                                      f"Stopped at step {i}: {result.error}", records)
            return TaskResult(task_id, "completed", "All steps completed.", records)
        finally:
            self._cancel.pop(task_id, None)

    def _emit(self, task_id: str, kind: str, tool: str, summary: str,
              step: int = 1, total: int = 1) -> None:
        try:
            self.on_event({"taskId": task_id, "type": kind, "tool": tool,
                           "summary": summary, "step": step, "total": total})
        except Exception:
            pass
