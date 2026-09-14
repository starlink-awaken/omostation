"""kairon-utils — General-purpose utilities for the kairon monorepo.

Provides logging, retry, rate limiting, error handling, concurrency,
deduplication, versioning, rollback, and SQLite utilities.
"""

from kairon_utils.append_only_log import AppendOnlyLog, fcntl_lock
from kairon_utils.atomic_write import atomic_write_json, atomic_write_text
from kairon_utils.concurrent import (
    ConcurrencyManager,
    ConcurrentBatchResult,
    ConcurrentResult,
    ProgressTracker,
    gather_with_concurrency,
)
from kairon_utils.deduplicator import ContentDeduplicator
from kairon_utils.error_classifier import ErrorCategory, ErrorClassifier, ErrorStatistics
from kairon_utils.error_handler import ErrorContext, ErrorHandler, create_error_handler, handle_exception
from kairon_utils.errors import (
    AgentTimeoutError,
    AgentToolkitError,
    AuthenticationError,
    ConfigurationError,
    LLMError,
    NetworkError,
    RateLimitError,
    RetryError,
    SessionError,
    ToolError,
    ValidationError,
    compress_error,
    get_error_message,
    is_retryable,
    wrap_error,
)
from kairon_utils.logging import JSONFormatter, LogContext, StructuredLogger, get_logger
from kairon_utils.rate_limiter import RateLimiter, TokenBucket
from kairon_utils.retry import CircuitBreaker, RetryExecutor, RetryPolicy
from kairon_utils.rollback import RollbackManager
from kairon_utils.sqlite_utils import managed_connection
from kairon_utils.versioning import ContentVersion, ContentVersionTracker

__all__ = [
    # atomic_write
    "atomic_write_json",
    "atomic_write_text",
    # append_only_log (B-1 P0 跨仓 SSOT)
    "AppendOnlyLog",
    "fcntl_lock",
    # concurrent
    "ConcurrencyManager",
    "ConcurrentBatchResult",
    "ConcurrentResult",
    "ProgressTracker",
    "gather_with_concurrency",
    # deduplicator
    "ContentDeduplicator",
    # error_classifier
    "ErrorCategory",
    "ErrorClassifier",
    "ErrorStatistics",
    # error_handler
    "ErrorContext",
    "ErrorHandler",
    "create_error_handler",
    "handle_exception",
    # errors
    "AgentTimeoutError",
    "AgentToolkitError",
    "AuthenticationError",
    "ConfigurationError",
    "LLMError",
    "NetworkError",
    "RateLimitError",
    "RetryError",
    "SessionError",
    "ToolError",
    "ValidationError",
    "compress_error",
    "get_error_message",
    "is_retryable",
    "wrap_error",
    # logging
    "JSONFormatter",
    "LogContext",
    "StructuredLogger",
    "get_logger",
    # rate_limiter
    "RateLimiter",
    "TokenBucket",
    # retry
    "CircuitBreaker",
    "RetryExecutor",
    "RetryPolicy",
    # rollback
    "RollbackManager",
    # sqlite_utils
    "managed_connection",
    # versioning
    "ContentVersion",
    "ContentVersionTracker",
]
