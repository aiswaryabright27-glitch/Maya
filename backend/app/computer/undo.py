"""Undo stack for reversible actions (file moves). In-memory + audit-backed."""
from __future__ import annotations

import shutil
import time
from pathlib import Path


class UndoStack:
    def __init__(self, limit: int = 50) -> None:
        self._stack: list[dict] = []
        self._limit = limit

    def push(self, entry: dict) -> None:
        entry.setdefault("ts", time.time())
        self._stack.append(entry)
        if len(self._stack) > self._limit:
            self._stack.pop(0)

    def pop(self) -> dict | None:
        return self._stack.pop() if self._stack else None

    def undo_last(self) -> dict:
        entry = self.pop()
        if entry is None:
            return {"ok": False, "error": "nothing to undo"}
        if entry.get("kind") != "file_moves":
            return {"ok": False, "error": f"cannot undo kind '{entry.get('kind')}'"}
        done, failed = 0, 0
        for inv in entry["inverse"]:
            src, dst = Path(inv["from"]), Path(inv["to"])
            try:
                if src.exists():
                    shutil.move(str(src), str(dst))
                    done += 1
                else:
                    failed += 1
            except OSError:
                failed += 1
        return {"ok": failed == 0, "undone": done, "failed": failed,
                "evidence": f"{done} moves reversed"}
