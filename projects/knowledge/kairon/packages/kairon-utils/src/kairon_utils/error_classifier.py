"""
Error Classification System.

Categorize errors for actionable response and recovery.
Extracted from D_Harvest utils/error_classifier.py.
"""

import asyncio
import logging
import traceback
from enum import Enum

_log = logging.getLogger(__name__)


class ErrorCategory(Enum):
    """Actionable error categories."""

    TRANSIENT = "transient"
    PERMANENT = "permanent"
    RATE_LIMIT = "rate_limit"
    AUTH_FAILURE = "auth"
    VALIDATION_ERROR = "validation"
    SYSTEM_ERROR = "system"


class ErrorClassifier:
    """Classify errors for actionable response."""

    ERROR_MAPPING: dict[type[Exception], ErrorCategory] = {
        TimeoutError: ErrorCategory.TRANSIENT,
        ConnectionError: ErrorCategory.TRANSIENT,
        PermissionError: ErrorCategory.AUTH_FAILURE,
        ValueError: ErrorCategory.VALIDATION_ERROR,
        KeyError: ErrorCategory.VALIDATION_ERROR,
        OSError: ErrorCategory.SYSTEM_ERROR,
    }

    def __init__(self) -> None:
        self._classification_cache: dict[str, ErrorCategory] = {}

    def classify(self, error: Exception) -> ErrorCategory:
        """
        Classify error into actionable category.

        Args:
            error: Exception to classify.

        Returns:
            ErrorCategory.
        """
        error_type = type(error)

        # Check direct mapping
        if error_type in self.ERROR_MAPPING:
            return self.ERROR_MAPPING[error_type]

        # Check HTTP errors
        if hasattr(error, "status"):
            status = getattr(error, "status", 0)
            if status == 429:
                return ErrorCategory.RATE_LIMIT
            elif 400 <= status < 500:
                return ErrorCategory.PERMANENT
            elif 500 <= status < 600:
                return ErrorCategory.TRANSIENT

        # Check for asyncio.TimeoutError
        if isinstance(error, asyncio.TimeoutError):
            return ErrorCategory.TRANSIENT

        # Default to system error
        return ErrorCategory.SYSTEM_ERROR

    def get_recovery_action(self, category: ErrorCategory) -> str:
        """
        Get recommended action for error category.

        Args:
            category: Error category.

        Returns:
            Recommended recovery action string.
        """
        actions = {
            ErrorCategory.TRANSIENT: "Retry with exponential backoff",
            ErrorCategory.PERMANENT: "Log and skip - manual intervention needed",
            ErrorCategory.RATE_LIMIT: "Back off and retry later",
            ErrorCategory.AUTH_FAILURE: "Refresh credentials and retry",
            ErrorCategory.VALIDATION_ERROR: "Fix input content and retry",
            ErrorCategory.SYSTEM_ERROR: "Alert operations team",
        }
        return actions.get(category, "Unknown error category")

    def should_retry(self, category: ErrorCategory) -> bool:
        """
        Determine if error is retryable.

        Args:
            category: Error category.

        Returns:
            True if error should be retried.
        """
        return category in {
            ErrorCategory.TRANSIENT,
            ErrorCategory.RATE_LIMIT,
            ErrorCategory.AUTH_FAILURE,
        }

    def classify_with_context(self, error: Exception, source_id: str) -> dict:
        """
        Classify error with full context.

        Args:
            error: Exception to classify.
            source_id: Affected source.

        Returns:
            Dictionary with classification results.
        """
        category = self.classify(error)

        return {
            "category": category.value,
            "retryable": self.should_retry(category),
            "action": self.get_recovery_action(category),
            "source_id": source_id,
            "error_type": type(error).__name__,
            "error_message": str(error),
            "traceback": traceback.format_exc() if _log.level <= logging.DEBUG else None,
        }

    def log_error(self, error: Exception, source_id: str) -> None:
        """
        Log classified error with context.

        Args:
            error: Exception to log.
            source_id: Affected source.
        """
        context = self.classify_with_context(error, source_id)

        if context["retryable"]:
            _log.warning(f"Retryable error for {source_id}: {context['category']} - {context['action']}")
        else:
            _log.error(f"Non-retryable error for {source_id}: {context['category']} - {context['action']}")


class ErrorStatistics:
    """Track error statistics for monitoring."""

    def __init__(self) -> None:
        self._counts: dict[str, dict[ErrorCategory, int]] = {}

    def record_error(self, source_id: str, category: ErrorCategory) -> None:
        """Record error occurrence."""
        if source_id not in self._counts:
            self._counts[source_id] = {}
        if category not in self._counts[source_id]:
            self._counts[source_id][category] = 0
        self._counts[source_id][category] += 1

    def get_statistics(self, source_id: str) -> dict[str, int]:
        """Get error statistics for a source."""
        if source_id not in self._counts:
            return {}
        return {category.value: count for category, count in self._counts[source_id].items()}

    def reset_statistics(self, source_id: str) -> None:
        """Reset statistics for a source."""
        if source_id in self._counts:
            del self._counts[source_id]
