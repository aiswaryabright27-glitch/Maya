from __future__ import annotations

import logging
import re
import traceback
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any


_SECRET_PATTERNS = (
    re.compile(r"(?i)(\bbearer\s+)([A-Za-z0-9._~+/-]+=*)"),
    re.compile(r"(?i)(\b[A-Z0-9_]*(?:API[_-]?KEY|ACCESS[_-]?TOKEN|AUTHORIZATION|PASSWORD|SECRET|BACKEND[_-]?TOKEN)\b\s*[:=]\s*)([^\s,;]+)"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b"),
)


def redact(value: Any) -> str:
    text = str(value)
    for pattern in _SECRET_PATTERNS:
        if pattern.groups:
            text = pattern.sub(lambda match: f"{match.group(1)}[REDACTED]", text)
        else:
            text = pattern.sub("[REDACTED]", text)
    return text


class RedactionFilter(logging.Filter):
    """Redact common credential forms from formatted messages and arguments."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            rendered = record.getMessage()
        except Exception:
            rendered = str(record.msg)
        record.msg = redact(rendered)
        record.args = ()
        if record.exc_info:
            record.exc_text = redact("".join(traceback.format_exception(*record.exc_info)))
            record.exc_info = None
        elif record.exc_text:
            record.exc_text = redact(record.exc_text)
        return True


def configure_logging(log_dir: Path) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)
    handler = logging.StreamHandler()
    handler.addFilter(RedactionFilter())
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    file_handler = RotatingFileHandler(log_dir / "maya.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8")
    file_handler.addFilter(RedactionFilter())
    file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.addHandler(file_handler)
    root.setLevel(logging.INFO)

