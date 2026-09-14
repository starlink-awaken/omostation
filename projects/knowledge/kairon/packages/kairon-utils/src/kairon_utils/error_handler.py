"""
Unified Error Handler.

Integrates error classification and structured logging to provide standardized
error handling. Ensures all errors are correctly classified, recorded, and reported.

Extracted from D_Harvest utils/error_handler.py.
"""

import logging
from datetime import UTC, datetime
from types import TracebackType

from kairon_utils.error_classifier import ErrorCategory, ErrorClassifier
from kairon_utils.logging import get_logger

_logger = get_logger(__name__)
ErrorContextData = dict[str, object]
ErrorResult = dict[str, object]


class ErrorHandler:
    """
    Unified error handler.

    Integrates error classification and structured logging, providing
    standardized error handling. Ensures all errors are correctly classified,
    recorded, and reported.
    """

    def __init__(self, component_name: str) -> None:
        """
        Initialize error handler.

        Args:
            component_name: Component name for log context.
        """
        self.component_name = component_name
        self.classifier = ErrorClassifier()
        self._error_counts: dict[ErrorCategory, int] = dict.fromkeys(ErrorCategory, 0)

    def handle_error(
        self,
        error: Exception,
        context: ErrorContextData | None = None,
        source_id: str | None = None,
        log_level: int = logging.ERROR,
    ) -> ErrorResult:
        """
        Unified error handling entry point.

        Args:
            error: Exception object.
            context: Additional context information.
            source_id: Source identifier (if available).
            log_level: Log level.

        Returns:
            Dictionary with error classification and recovery suggestions.
        """
        category = self.classifier.classify(error)
        self._error_counts[category] += 1

        recovery_action = self.classifier.get_recovery_action(category)
        is_retryable = self.classifier.should_retry(category)

        log_context = {
            "component": self.component_name,
            "error_category": category.value,
            "error_type": type(error).__name__,
            "error_message": str(error),
            "retryable": is_retryable,
            "recovery_action": recovery_action,
            "timestamp": datetime.now(UTC).isoformat(),
        }

        if context:
            log_context.update(context)  # type: ignore[arg-type]

        if source_id:
            log_context["source_id"] = source_id

        if category in (ErrorCategory.TRANSIENT, ErrorCategory.RATE_LIMIT):
            _logger.warning(
                f"Retryable error in {self.component_name}: {category.value} - {recovery_action}",
                context=log_context,  # type: ignore[arg-type]
            )
        elif category == ErrorCategory.VALIDATION_ERROR:
            _logger.warning(f"Validation error in {self.component_name}: {type(error).__name__}", context=log_context)  # type: ignore[arg-type]
        else:
            _logger.error(
                f"Non-retryable error in {self.component_name}: {category.value}",
                context=log_context,  # type: ignore[arg-type]
                exc_info=error,
            )

        return {
            "category": category,
            "retryable": is_retryable,
            "action": recovery_action,
            "context": log_context,
        }

    # -- Domain-specific convenience logging methods (adapted to generic StructuredLogger) --

    def log_harvest_start(self, source_id: str, priority: str = "normal") -> None:
        """Log operation start."""
        _logger.info(
            f"Operation started for {source_id}",
            context={"source_id": source_id, "priority": priority, "event": "operation_started"},
        )

    def log_harvest_success(self, source_id: str, items_count: int, duration_ms: float) -> None:
        """Log operation success."""
        _logger.info(
            f"Operation completed for {source_id}: {items_count} items in {duration_ms:.2f}ms",
            context={
                "source_id": source_id,
                "items_count": items_count,
                "duration_ms": duration_ms,
                "event": "operation_completed",
            },
        )

    def log_harvest_failure(self, source_id: str, error: Exception) -> None:
        """Log operation failure."""
        result = self.handle_error(error, source_id=source_id)
        _logger.error(
            f"Operation failed for {source_id}: {error}",
            context={
                "source_id": source_id,
                "error_type": result["category"].value,  # type: ignore[attr-defined]
                "event": "operation_failed",
            },
        )

    def log_quality_gate_rejection(self, source_id: str, score: float, reason: str) -> None:
        """Log quality gate rejection."""
        _logger.warning(
            f"Quality gate rejected {source_id}: score={score}, reason={reason}",
            context={"source_id": source_id, "score": score, "reason": reason, "event": "quality_rejected"},
        )

    def log_checkpoint_saved(self, source_id: str, step: str) -> None:
        """Log checkpoint save."""
        _logger.debug(
            f"Checkpoint saved for {source_id} at {step}",
            context={"source_id": source_id, "step": step, "event": "checkpoint_saved"},
        )

    def log_rate_limit_exceeded(self, source_id: str, retry_after: int | None = None) -> None:
        """Log rate limit exceeded."""
        _logger.warning(
            f"Rate limit exceeded for {source_id}",
            context={"source_id": source_id, "retry_after": retry_after, "event": "rate_limited"},
        )

    def get_error_statistics(self) -> dict[str, int]:
        """Get error statistics."""
        return {category.value: count for category, count in self._error_counts.items()}

    def reset_error_statistics(self) -> None:
        """Reset error statistics."""
        self._error_counts = dict.fromkeys(ErrorCategory, 0)


def create_error_handler(component_name: str) -> ErrorHandler:
    """
    Create an ErrorHandler instance.

    Args:
        component_name: Component name.

    Returns:
        ErrorHandler instance.
    """
    return ErrorHandler(component_name)


def handle_exception(
    error: Exception,
    component: str,
    context: ErrorContextData | None = None,
    source_id: str | None = None,
) -> ErrorResult:
    """
    Convenience function for quick exception handling.

    Args:
        error: Exception object.
        component: Component name.
        context: Additional context.
        source_id: Source identifier.

    Returns:
        Error handling result dictionary.
    """
    handler = create_error_handler(component)
    return handler.handle_error(error, context, source_id)


class ErrorContext:
    """
    Error context manager.

    Automatically captures and handles exceptions, ensuring errors are
    correctly recorded and classified.
    """

    def __init__(
        self,
        component_name: str,
        context: ErrorContextData | None = None,
        source_id: str | None = None,
        reraise: bool = False,
    ) -> None:
        """
        Initialize error context.

        Args:
            component_name: Component name.
            context: Additional context.
            source_id: Source identifier.
            reraise: Whether to re-raise exceptions.
        """
        self.component_name = component_name
        self.context = context or {}
        self.source_id = source_id
        self.reraise = reraise
        self.handler = create_error_handler(component_name)
        self.error_occurred = False
        self.error_result: ErrorResult | None = None

    def __enter__(self) -> "ErrorContext":
        """Enter context."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> bool:
        """Exit context."""
        if exc_type is not None:
            self.error_occurred = True
            error = exc_val

            self.error_result = self.handler.handle_error(error, context=self.context, source_id=self.source_id)  # type: ignore[arg-type]

            if not self.reraise:
                return True  # Suppress exception

        return False  # Do not suppress

    def get_error_result(self) -> ErrorResult | None:
        """Get error handling result."""
        return self.error_result
