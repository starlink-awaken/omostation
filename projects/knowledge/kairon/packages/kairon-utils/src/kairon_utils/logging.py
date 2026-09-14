"""
Structured JSON Logging.

Provides structured JSON logging with consistent formatting and fields.
Extracted from D_Harvest utils/logging.py.

All logs include timestamp, level, component, and contextual data.
"""

import json
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType

LogContext = dict[str, object]
ExcInfoType = BaseException | tuple[type[BaseException], BaseException, TracebackType | None] | bool


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter with consistent field ordering."""

    def __init__(self, component: str = "kairon") -> None:
        super().__init__()
        self.component = component

    def format(self, record: logging.LogRecord) -> str:
        """
        Format log record as JSON.

        Fields:
        - timestamp: ISO 8601 timestamp
        - level: Log level
        - component: Component identifier
        - logger: Logger name
        - message: Log message
        - module: Module name
        - function: Function name
        - line: Line number
        - context: Additional contextual data (if provided)
        - exception: Exception info (if exception occurred)
        """
        log_entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "component": self.component,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        if hasattr(record, "context"):
            log_entry["context"] = record.context  # type: ignore[reportAttributeAccessIssue]

        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry, default=str)


class StructuredLogger:
    """
    Structured logger with domain-specific logging methods.

    Provides configurable component identifier and optional file output.
    """

    def __init__(self, name: str, component: str = "kairon", log_file: Path | None = None) -> None:
        """
        Initialize structured logger.

        Args:
            name: Logger name (usually module path).
            component: Component identifier for log attribution.
            log_file: Optional file handler for output.
        """
        self._logger = logging.getLogger(name)
        self._logger.setLevel(logging.DEBUG)

        # Remove existing handlers
        self._logger.handlers.clear()

        # Console handler with JSON formatter
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(JSONFormatter(component))
        self._logger.addHandler(console_handler)

        # Optional file handler
        if log_file:
            log_file.parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(str(log_file))
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(JSONFormatter(component))
            self._logger.addHandler(file_handler)

    def _log_with_context(self, level: int, message: str, context: LogContext | None = None) -> None:
        """Log message with optional context."""
        extra = {"context": context} if context else {}
        self._logger.log(level, message, extra=extra)

    def debug(self, message: str, context: LogContext | None = None) -> None:
        """Log debug message."""
        self._log_with_context(logging.DEBUG, message, context)

    def info(self, message: str, context: LogContext | None = None) -> None:
        """Log info message."""
        self._log_with_context(logging.INFO, message, context)

    def warning(self, message: str, context: LogContext | None = None) -> None:
        """Log warning message."""
        self._log_with_context(logging.WARNING, message, context)

    def error(
        self,
        message: str,
        context: LogContext | None = None,
        exc_info: ExcInfoType | None = None,
    ) -> None:
        """Log error message."""
        if exc_info:
            self._logger.error(message, exc_info=exc_info, extra={"context": context} if context else {})
        else:
            self._log_with_context(logging.ERROR, message, context)

    def critical(
        self,
        message: str,
        context: LogContext | None = None,
        exc_info: ExcInfoType | None = None,
    ) -> None:
        """Log critical message."""
        if exc_info:
            self._logger.critical(message, exc_info=exc_info, extra={"context": context} if context else {})
        else:
            self._log_with_context(logging.CRITICAL, message, context)


def get_logger(name: str, component: str = "kairon", log_file: Path | None = None) -> StructuredLogger:
    """
    Get or create a structured logger for a module.

    Args:
        name: Logger name (usually __name__).
        component: Component identifier.
        log_file: Optional file for log output.

    Returns:
        StructuredLogger instance.
    """
    return StructuredLogger(name, component, log_file)
