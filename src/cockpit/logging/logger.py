"""Structured logging and tracing for Cockpit CLI."""

from __future__ import annotations

import logging
import os
import sys
import uuid
from typing import Any

_TRACE_ID_VAR = "COCKPIT_TRACE_ID"


def get_or_create_trace_id() -> str:
    """Retrieve the active trace ID from environment or generate a new one."""
    tid = os.environ.get(_TRACE_ID_VAR)
    if not tid:
        tid = f"trc-{uuid.uuid4().hex[:12]}"
        os.environ[_TRACE_ID_VAR] = tid
    return tid


class CockpitLogger:
    """Unified logger with trace-id enrichment and non-intrusive terminal handling."""

    def __init__(self, name: str = "cockpit"):
        self.logger = logging.getLogger(name)
        self.trace_id = get_or_create_trace_id()

    def debug(self, msg: str, **kwargs: Any) -> None:
        self.logger.debug(f"[{self.trace_id}] {msg}", extra=kwargs)

    def info(self, msg: str, **kwargs: Any) -> None:
        self.logger.info(f"[{self.trace_id}] {msg}", extra=kwargs)

    def warning(self, msg: str, **kwargs: Any) -> None:
        self.logger.warning(f"[{self.trace_id}] {msg}", extra=kwargs)

    def error(self, msg: str, **kwargs: Any) -> None:
        self.logger.error(f"[{self.trace_id}] {msg}", extra=kwargs)


def get_logger(name: str = "cockpit") -> CockpitLogger:
    """Obtain a CockpitLogger instance."""
    return CockpitLogger(name)
