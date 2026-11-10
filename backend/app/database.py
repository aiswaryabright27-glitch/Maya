from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path


MIGRATIONS_DIR = Path(__file__).with_name("migrations")


def migrate_database(database_path: Path) -> list[int]:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    applied_now: list[int] = []
    with sqlite3.connect(database_path, timeout=10) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            "version INTEGER PRIMARY KEY, checksum TEXT NOT NULL, applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
        )
        for migration in sorted(MIGRATIONS_DIR.glob("[0-9][0-9][0-9]_*.sql")):
            version = int(migration.name[:3])
            sql = migration.read_text(encoding="utf-8")
            checksum = hashlib.sha256(sql.encode("utf-8")).hexdigest()
            existing = connection.execute(
                "SELECT checksum FROM schema_migrations WHERE version = ?", (version,)
            ).fetchone()
            if existing:
                if existing[0] != checksum:
                    raise RuntimeError(f"Migration {version:03d} changed after it was applied")
                continue
            # Apply the DDL and migration record atomically.
            connection.executescript(
                "BEGIN IMMEDIATE;\n"
                + sql
                + "\nINSERT INTO schema_migrations(version, checksum) VALUES ("
                + str(version)
                + ", '"
                + checksum
                + "');\nCOMMIT;"
            )
            applied_now.append(version)
    return applied_now

