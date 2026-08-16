from __future__ import annotations

"""Error types and error handling utilities.

Migrated from agentmesh/packages/toolkit/src/errors/.

Provides:
- AgentToolkitError: base error class
- Specialized error types (LLM, Validation, Network, Timeout, Auth, etc.)
- Utility functions: is_retryable, get_error_message, wrap_error, compress_error
"""

import math
import time
from typing import Any

# ---------------------------------------------------------------------------
# Error class hierarchy
# ---------------------------------------------------------------------------


class AgentToolkitError(Exception):
    """Base error for the agent toolkit."""

    def __init__(
        self,
        message: str,
        code: str = "UNKNOWN_ERROR",
        *,
        status_code: int | None = None,
        details: Any = None,
        cause: BaseException | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code
        self.details = details
        self.timestamp = time.time()
        if cause is not None:
            self.__cause__ = cause

    def to_json(self) -> dict[str, Any]:
        return {
            "name": type(self).__name__,
            "message": self.args[0] if self.args else "",
            "code": self.code,
            "status_code": self.status_code,
            "details": self.details,
            "timestamp": self.timestamp,
        }


class LLMError(AgentToolkitError):
    def __init__(self, message: str, **kwargs: Any) -> None:
        super().__init__(message, "LLM_ERROR", **kwargs)


class ValidationError(AgentToolkitError):
    def __init__(self, message: str, **kwargs: Any) -> None:
        super().__init__(message, "VALIDATION_ERROR", **kwargs)


class ConfigurationError(AgentToolkitError):
    def __init__(self, message: str, **kwargs: Any) -> None:
        super().__init__(message, "CONFIGURATION_ERROR", **kwargs)


class NetworkError(AgentToolkitError):
    def __init__(self, message: str, **kwargs: Any) -> None:
        super().__init__(message, "NETWORK_ERROR", **kwargs)


class AgentTimeoutError(AgentToolkitError):
    def __init__(self, message: str, **kwargs: Any) -> None:
        super().__init__(message, "TIMEOUT_ERROR", **kwargs)


class AuthenticationError(AgentToolkitError):
    def __init__(self, message: str, **kwargs: Any) -> None:
        super().__init__(message, "AUTHENTICATION_ERROR", **kwargs)


class RateLimitError(AgentToolkitError):
    def __init__(self, message: str, *, retry_after: float | None = None, **kwargs: Any) -> None:
        super().__init__(message, "RATE_LIMIT_ERROR", **kwargs)
        self.retry_after = retry_after


class SessionError(AgentToolkitError):
    def __init__(self, message: str, **kwargs: Any) -> None:
        super().__init__(message, "SESSION_ERROR", **kwargs)


class ToolError(AgentToolkitError):
    def __init__(self, message: str, **kwargs: Any) -> None:
        super().__init__(message, "TOOL_ERROR", **kwargs)


class RetryError(AgentToolkitError):
    def __init__(self, message: str, *, attempts: int = 1, **kwargs: Any) -> None:
        super().__init__(message, "RETRY_ERROR", **kwargs)
        self.attempts = attempts


# Extensible error registry
ERROR_REGISTRY: dict[str, type[AgentToolkitError]] = {
    "LLM_ERROR": LLMError,
    "VALIDATION_ERROR": ValidationError,
    "CONFIGURATION_ERROR": ConfigurationError,
    "NETWORK_ERROR": NetworkError,
    "TIMEOUT_ERROR": AgentTimeoutError,
    "AUTHENTICATION_ERROR": AuthenticationError,
    "RATE_LIMIT_ERROR": RateLimitError,
    "SESSION_ERROR": SessionError,
    "TOOL_ERROR": ToolError,
    "RETRY_ERROR": RetryError,
}


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------

RETRYABLE_CODES = frozenset({"NETWORK_ERROR", "TIMEOUT_ERROR", "RATE_LIMIT_ERROR"})
RETRYABLE_STATUS_CODES = frozenset({408, 429, 500, 502, 503, 504})


def is_retryable(error: Any) -> bool:
    """Return True if the error is eligible for retry."""
    if isinstance(error, AgentToolkitError):
        if error.code in RETRYABLE_CODES:
            return True
        if error.code in ("AUTHENTICATION_ERROR", "VALIDATION_ERROR", "CONFIGURATION_ERROR"):
            return False
        if error.status_code is not None and error.status_code in RETRYABLE_STATUS_CODES:
            return True
    return False


def get_error_message(error: Any) -> str:
    """Return a user-friendly error message."""
    friendly: dict[str, str] = {
        "NETWORK_ERROR": "网络连接失败，请检查网络后重试",
        "TIMEOUT_ERROR": "操作超时，请稍后重试",
        "AUTHENTICATION_ERROR": "认证失败，请检查密钥或权限",
        "RATE_LIMIT_ERROR": "请求频率过高，请稍后重试",
        "VALIDATION_ERROR": "输入数据验证失败，请检查输入格式",
        "CONFIGURATION_ERROR": "配置错误，请检查配置文件",
        "LLM_ERROR": "AI服务调用失败，请稍后重试",
    }
    if isinstance(error, AgentToolkitError):
        return friendly.get(error.code, error.args[0] if error.args else "发生未知错误")
    if isinstance(error, Exception):
        return str(error) or "发生未知错误"
    if isinstance(error, str):
        return error
    return "发生未知错误"


def wrap_error(
    error: Any, code: str = "UNKNOWN_ERROR", message: str = "An unexpected error occurred"
) -> AgentToolkitError:
    """Wrap an arbitrary error into an AgentToolkitError."""
    if isinstance(error, AgentToolkitError):
        return error
    if isinstance(error, Exception):
        return AgentToolkitError(str(error), code, cause=error)
    if isinstance(error, str):
        return AgentToolkitError(error, code)
    return AgentToolkitError(message, code, details=error)


def compress_error(error: Any) -> dict[str, Any]:
    """Compress error info into a minimal dict for logging / transport."""
    ts = time.time()
    if isinstance(error, AgentToolkitError):
        return {"type": type(error).__name__, "code": error.code, "message": str(error.args[0])[:200], "timestamp": ts}
    if isinstance(error, Exception):
        return {"type": type(error).__name__, "message": str(error)[:200], "timestamp": ts}
    if isinstance(error, str):
        return {"type": "StringError", "message": error[:200], "timestamp": ts}
    return {"type": "UnknownError", "message": "Unknown error occurred", "timestamp": ts}


def calculate_retry_delay(error: Any, attempt: int, base_delay: float = 1.0, max_delay: float = 30.0) -> float:
    """Calculate exponential backoff delay in seconds."""
    if isinstance(error, RateLimitError) and error.retry_after is not None and error.retry_after > 0:
        return min(error.retry_after, max_delay)
    delay = base_delay * math.pow(2, attempt - 1)
    return min(delay, max_delay)
