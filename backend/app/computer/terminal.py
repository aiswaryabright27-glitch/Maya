"""Allowlisted terminal commands. No shell interpolation, cwd-bounded, capped."""
from __future__ import annotations

import os
import re
import subprocess
import time
from pathlib import Path

# command prefix -> allowed arg pattern (full match on joined args)
ALLOWLIST: dict[str, re.Pattern] = {
    "python": re.compile(r"^[\w./\\-]+(\.py)?( [\w./\\: -]+)?$"),
    "python3": re.compile(r"^[\w./\\-]+(\.py)?( [\w./\\: -]+)?$"),
    "pip": re.compile(r"^(install|list|show|freeze)[\w ./\\-]*$"),
    "npm": re.compile(r"^(run [\w:-]+|test|start|install|ls|ci)[\w ./\\-]*$"),
    "git": re.compile(r"^(status|log|diff|branch|add|commit|pull|push|checkout|clone)[\w ./\\:,-]*$"),
    "dir": re.compile(r"^[\w ./\\*-]*$"),
    "ls": re.compile(r"^[\w ./\\*-]*$"),
    "echo": re.compile(r"^[\w .,;:!?()'\"-]{0,200}$"),
    "type": re.compile(r"^[\w ./\\-]{1,200}$"),
    "cat": re.compile(r"^[\w ./\\-]{1,200}$"),
    "where": re.compile(r"^[\w .-]{1,100}$"),
}

DENYLIST = re.compile(r"(?i)(rm\s+-rf|del\s+/[sq]|format\s+[a-z]:|shutdown|reg\s+delete|net\s+user|curl\s+.*\|\s*sh|invoke-expression|iex\b)")

MAX_OUTPUT = 20_000
DEFAULT_TIMEOUT = 30


def allowed_roots(extra: list[str] | None = None) -> list[Path]:
    roots = [Path.home(), Path(os.environ.get("USERPROFILE", str(Path.home())))]
    roots += [Path(p) for p in (extra or [])]
    return [r.resolve() for r in roots]


def check_command(command: str, args: str, cwd: str | None) -> tuple[bool, str]:
    full = f"{command} {args}".strip()
    if DENYLIST.search(full):
        return False, "command matches denylist"
    pattern = ALLOWLIST.get(command.lower())
    if pattern is None:
        return False, f"command '{command}' is not on the allowlist"
    if not pattern.match(args.strip() or "$") and args.strip():
        return False, f"arguments for '{command}' failed validation"
    if cwd:
        try:
            resolved = Path(cwd).expanduser().resolve()
            if not any(str(resolved).lower().startswith(str(r).lower()) for r in allowed_roots()):
                return False, "working directory outside allowed roots"
        except OSError:
            return False, "invalid working directory"
    return True, "ok"


def run_command(command: str, args: str = "", cwd: str | None = None,
                timeout: int = DEFAULT_TIMEOUT) -> dict:
    ok, reason = check_command(command, args, cwd)
    if not ok:
        return {"ok": False, "error": reason, "evidence": "allowlist rejected"}
    argv = [command] + ([args] if args else [])
    # args is a single string; split safely on whitespace for simple commands
    argv = [command] + args.split() if args else [command]
    try:
        proc = subprocess.run(argv, cwd=cwd, capture_output=True, text=True,
                              timeout=min(timeout, 120), shell=False,
                              errors="replace")
        out = (proc.stdout or "")[-MAX_OUTPUT:]
        err = (proc.stderr or "")[-MAX_OUTPUT:]
        return {"ok": proc.returncode == 0, "exit_code": proc.returncode,
                "stdout": out, "stderr": err,
                "evidence": f"exit_code={proc.returncode}"}
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"timed out after {timeout}s", "evidence": "timeout"}
    except OSError as exc:
        return {"ok": False, "error": f"cannot execute: {type(exc).__name__}", "evidence": "spawn failed"}
