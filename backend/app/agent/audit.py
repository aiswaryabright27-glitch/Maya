"""Append-only audit log in SQLite. Never stores secrets or full payloads."""
from __future__ import annotations

import json
import re
import sqlite3
import time
from pathlib import Path
from typing import Any

_SECRET_KEY = re.compile(r"(?i)(key|token|secret|password|authorization|credential)")


def summarize_args(args: dict[str, Any], limit: int = 400) -> str:
    """JSON summary with secret-looking keys masked and length capped."""
    safe: dict[str, Any] = {}
    for key, value in args.items():
        if _SECRET_KEY.search(str(key)):
            safe[key] = "[REDACTED]"
        else:
            safe[key] = value if isinstance(value, (str, int, float, bool)) else str(value)[:120]
    text = json.dumps(safe, ensure_ascii=False)
    return text[:limit]


class AuditLog:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._init()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS audit_log(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts REAL NOT NULL,
                    task_id TEXT,
                    tool TEXT NOT NULL,
                    args_summary TEXT NOT NULL,
                    decision TEXT NOT NULL,
                    result TEXT,
                    provenance TEXT
                )"""
            )

    def record(self, tool: str, args: dict[str, Any], decision: str,
               result: str | None = None, task_id: str | None = None,
               provenance: str | None = None) -> int:
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO audit_log(ts, task_id, tool, args_summary, decision, result, provenance) VALUES (?,?,?,?,?,?,?)",
                (time.time(), task_id, tool, summarize_args(args), decision, (result or "")[:500], provenance),
            )
            return int(cur.lastrowid)

    def query(self, task_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        with self._connect() as conn:
            if task_id:
                rows = conn.execute(
                    "SELECT * FROM audit_log WHERE task_id=? ORDER BY id DESC LIMIT ?", (task_id, limit)
                ).fetchall()
            else:
                rows = conn.execute("SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(row) for row in rows]
