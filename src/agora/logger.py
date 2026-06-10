"""Simple logging wrapper for agentmesh gateway migration.

Provides configurable logging with support for structured data output.
Adapted from agentmesh gateway core/logger.ts.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any


class Logger:
    """Simple structured logger wrapping Python's logging."""

    def __init__(self, name: str = "agora"):
        self._log = logging.getLogger(name)

    def debug(self, msg: str, data: dict[str, Any] | None = None) -> None:
        self._log.debug(self._fmt(msg, data))

    def info(self, msg: str, data: dict[str, Any] | None = None) -> None:
        self._log.info(self._fmt(msg, data))

    def warn(self, msg: str, data: dict[str, Any] | None = None) -> None:
        self._log.warning(self._fmt(msg, data))

    def error(self, msg: str, data: dict[str, Any] | None = None) -> None:
        self._log.error(self._fmt(msg, data))

    @staticmethod
    def _fmt(msg: str, data: dict[str, Any] | None) -> str:
        return f"{msg} {data!s}" if data else msg


_logger: Logger | None = None


def init_logger(
    level: str = "info",
    log_dir: str | None = None,
    name: str = "agora",
) -> None:
    """Initialize the global logger.

    Args:
        level: One of debug, info, warn, error.
        log_dir: Optional directory for log file output.
        name: Logger name.
    """
    global _logger
    _logger = Logger(name)

    log_level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        stream=sys.stderr,
    )

    if log_dir:
        log_path = Path(log_dir)
        log_path.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(str(log_path / "agora.log"))
        fh.setLevel(log_level)
        fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
        logging.getLogger(name).addHandler(fh)


def get_logger(name: str = "agora") -> Logger:
    """Get the global or a named logger instance."""
    if _logger is not None and name == "agora":
        return _logger
    return Logger(name)


logger = get_logger()
