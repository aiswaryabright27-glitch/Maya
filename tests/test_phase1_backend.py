from __future__ import annotations

import logging
import os
import sqlite3
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("MAYA_BACKEND_TOKEN", "test-import-token-not-a-secret-000000")
os.environ.setdefault("MAYA_DATA_DIR", str(Path(tempfile.gettempdir()) / "maya-phase1-tests"))

from app.config import Settings  # noqa: E402
from app.database import migrate_database  # noqa: E402
from app.logging_config import RedactionFilter  # noqa: E402
from app.main import create_app  # noqa: E402


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        host="127.0.0.1",
        port=9876,
        backend_token="unit-test-token-value-000000000000000000000000",
        mode="mock",
        data_dir=tmp_path,
    )


def test_environment_configuration_rejects_invalid_values(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("MAYA_HOST", "0.0.0.0")
    monkeypatch.setenv("MAYA_PORT", "8765")
    monkeypatch.setenv("MAYA_MODE", "live")
    monkeypatch.setenv("MAYA_BACKEND_TOKEN", "would-be-secret-value-123456789012")
    monkeypatch.setenv("MAYA_DATA_DIR", str(tmp_path))
    with pytest.raises(RuntimeError) as error:
        Settings.from_environment()
    assert "would-be-secret-value" not in str(error.value)
    assert "Invalid Maya environment configuration" in str(error.value)


def test_database_migrations_apply_once_and_create_audit_table(tmp_path: Path) -> None:
    database_path = tmp_path / "db" / "maya.db"
    assert migrate_database(database_path) == [1]
    assert migrate_database(database_path) == []
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "INSERT INTO audit_events(event_type, decision, summary) VALUES (?, ?, ?)",
            ("startup", "allowed", "backend started"),
        )
        assert connection.execute("SELECT COUNT(*) FROM audit_events").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0] == 1


def test_health_endpoint_requires_token_and_confirms_database(settings: Settings) -> None:
    with TestClient(create_app(settings)) as client:
        assert client.get("/healthz").status_code == 401
        assert client.get("/healthz", headers={"Authorization": "Bearer wrong"}).status_code == 401
        response = client.get(
            "/healthz",
            headers={"Authorization": f"Bearer {settings.backend_token.get_secret_value()}"},
        )
        assert response.status_code == 200
        assert response.json() == {
            "ok": True,
            "mode": "mock",
            "database_ready": True,
            "capabilities": ["speech.mock", "llm.mock"],
        }


def test_redaction_filter_removes_secret_patterns(caplog: pytest.LogCaptureFixture) -> None:
    logger = logging.getLogger("maya.test.redaction")
    handler = logging.StreamHandler()
    handler.addFilter(RedactionFilter())
    logger.addHandler(handler)
    try:
        with caplog.at_level(logging.INFO, logger=logger.name):
            logger.info("GNANI_API_KEY=%s authorization=%s", "test-key-987654", "Bearer abcdefghijklmnop")
            try:
                raise RuntimeError("OPENAI_API_KEY=exception-secret-012345")
            except RuntimeError:
                logger.exception("provider startup failed")
        assert "test-key-987654" not in caplog.text
        assert "abcdefghijklmnop" not in caplog.text
        assert "exception-secret-012345" not in caplog.text
        assert "[REDACTED]" in caplog.text
    finally:
        logger.removeHandler(handler)


def test_migration_checksum_drift_is_rejected(tmp_path: Path) -> None:
    database_path = tmp_path / "maya.db"
    migrate_database(database_path)
    with sqlite3.connect(database_path) as connection:
        connection.execute("UPDATE schema_migrations SET checksum = 'stale'")
    with pytest.raises(RuntimeError, match="changed after it was applied"):
        migrate_database(database_path)
