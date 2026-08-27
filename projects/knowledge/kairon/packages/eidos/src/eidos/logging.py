"""Structured logging for Eidos.

Usage:
    from eidos.logging import logger
    logger.info("validate", file="data.json", type="KnowledgeCard", result="pass")
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any


class StructuredFormatter(logging.Formatter):
    """Output logs as JSON lines for machine parsing."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if hasattr(record, "structured"):
            log_entry.update(record.structured)  # type: ignore[reportAttributeAccessIssue]
        return json.dumps(log_entry, ensure_ascii=False)


def _get_logger(name: str = "eidos") -> logging.Logger:
    """Get a structured logger."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(StructuredFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger


logger = _get_logger()


def _log(level: str, message: str, **kwargs: Any) -> None:
    """Log a structured message."""
    extra = {"structured": kwargs}
    getattr(logger, level, logger.info)(message, extra=extra)
