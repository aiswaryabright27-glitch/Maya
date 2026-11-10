"""Project registry: name, path, aliases, approved commands. SQLite-backed."""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path


class ProjectRegistry:
    def __init__(self, db_path: Path) -> None:
        self._db = db_path
        self._init()

    def _connect(self):
        conn = sqlite3.connect(self._db)
        conn.row_factory = sqlite3.Row
        return conn

    def _init(self) -> None:
        self._db.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS projects(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL, path TEXT NOT NULL,
                aliases TEXT NOT NULL DEFAULT '[]',
                commands TEXT NOT NULL DEFAULT '{}',
                editor TEXT, created REAL NOT NULL)""")

    def register(self, name: str, path: str, aliases: list[str] | None = None,
                 commands: dict | None = None, editor: str | None = None) -> dict:
        p = Path(path).expanduser()
        if not p.is_dir():
            return {"ok": False, "error": f"path does not exist: {path}"}
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO projects(name,path,aliases,commands,editor,created) VALUES(?,?,?,?,?,?)",
                (name, str(p.resolve()), json.dumps(aliases or []),
                 json.dumps(commands or {}), editor, time.time()))
        return {"ok": True, "name": name, "path": str(p.resolve())}

    def list(self) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM projects").fetchall()
        return [{"id": r["id"], "name": r["name"], "path": r["path"],
                 "aliases": json.loads(r["aliases"]), "commands": json.loads(r["commands"]),
                 "editor": r["editor"]} for r in rows]

    def resolve(self, spoken: str) -> dict | None:
        """Match spoken name/alias case-insensitively; None if ambiguous/unknown."""
        q = spoken.strip().lower()
        matches = []
        for p in self.list():
            names = [p["name"].lower()] + [a.lower() for a in p["aliases"]]
            if any(q == n or q in n or n in q for n in names if n):
                matches.append(p)
        if len(matches) == 1:
            return matches[0]
        return None if not matches else {"ambiguous": [m["name"] for m in matches]}
