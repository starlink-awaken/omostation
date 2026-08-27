"""Tests for kairon_lib.errors — error hierarchy and error utilities."""
# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false

from kairon_utils.errors import (
    ERROR_REGISTRY,
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
    calculate_retry_delay,
    compress_error,
    get_error_message,
    is_retryable,
    wrap_error,
)


class TestAgentToolkitError:
    def test_creation_with_minimal_args(self):
        err = AgentToolkitError("something went wrong")
        assert str(err) == "something went wrong"
        assert err.code == "UNKNOWN_ERROR"
        assert err.status_code is None
        assert err.timestamp > 0

    def test_creation_with_all_args(self):
        cause = ValueError("root cause")
        err = AgentToolkitError("bad", "CUSTOM_CODE", status_code=400, details={"key": "val"}, cause=cause)
        assert err.code == "CUSTOM_CODE"
        assert err.status_code == 400
        assert err.details == {"key": "val"}
        assert err.__cause__ is cause

    def test_to_json(self):
        err = AgentToolkitError("msg", "ERR", status_code=500)
        j = err.to_json()
        assert j["name"] == "AgentToolkitError"
        assert j["message"] == "msg"
        assert j["code"] == "ERR"
        assert j["status_code"] == 500


class TestSpecializedErrors:
    def test_llm_error(self):
        err = LLMError("LLM failed", status_code=503)
        assert err.code == "LLM_ERROR"
        assert err.status_code == 503

    def test_validation_error(self):
        err = ValidationError("invalid input")
        assert err.code == "VALIDATION_ERROR"

    def test_configuration_error(self):
        err = ConfigurationError("bad config")
        assert err.code == "CONFIGURATION_ERROR"

    def test_network_error(self):
        err = NetworkError("connection refused")
        assert err.code == "NETWORK_ERROR"

    def test_timeout_error(self):
        err = AgentTimeoutError("timed out")
        assert err.code == "TIMEOUT_ERROR"

    def test_authentication_error(self):
        err = AuthenticationError("unauthorized")
        assert err.code == "AUTHENTICATION_ERROR"

    def test_rate_limit_error_with_retry_after(self):
        err = RateLimitError("too fast", retry_after=30.0)
        assert err.code == "RATE_LIMIT_ERROR"
        assert err.retry_after == 30.0

    def test_rate_limit_error_without_retry_after(self):
        err = RateLimitError("too fast")
        assert err.retry_after is None

    def test_session_error(self):
        err = SessionError("session expired")
        assert err.code == "SESSION_ERROR"

    def test_tool_error(self):
        err = ToolError("tool crashed")
        assert err.code == "TOOL_ERROR"

    def test_retry_error_with_attempts(self):
        err = RetryError("exhausted", attempts=3)
        assert err.code == "RETRY_ERROR"
        assert err.attempts == 3

    def test_error_registry_contains_all_types(self):
        assert ERROR_REGISTRY["LLM_ERROR"] is LLMError
        assert ERROR_REGISTRY["VALIDATION_ERROR"] is ValidationError
        assert ERROR_REGISTRY["NETWORK_ERROR"] is NetworkError
        assert ERROR_REGISTRY["RETRY_ERROR"] is RetryError
        assert len(ERROR_REGISTRY) == 10


class TestIsRetryable:
    def test_retryable_codes(self):
        assert is_retryable(NetworkError("fail")) is True
        assert is_retryable(AgentTimeoutError("timeout")) is True
        assert is_retryable(RateLimitError("throttle")) is True

    def test_non_retryable_codes(self):
        assert is_retryable(AuthenticationError("auth")) is False
        assert is_retryable(ValidationError("val")) is False
        assert is_retryable(ConfigurationError("config")) is False

    def test_retryable_by_status_code(self):
        err = AgentToolkitError("server err", status_code=502)
        assert is_retryable(err) is True

    def test_non_retryable_by_status_code(self):
        err = AgentToolkitError("bad request", status_code=400)
        assert is_retryable(err) is False

    def test_non_error_object(self):
        assert is_retryable("just a string") is False
        assert is_retryable(42) is False


class TestGetErrorMessage:
    def test_known_code_returns_friendly(self):
        err = NetworkError("original")
        msg = get_error_message(err)
        assert "网络连接失败" in msg

    def test_unknown_code_returns_original_message(self):
        err = AgentToolkitError("custom failure message", code="UNKNOWN")
        msg = get_error_message(err)
        assert msg == "custom failure message"

    def test_plain_exception(self):
        msg = get_error_message(ValueError("bad value"))
        assert msg == "bad value"

    def test_string_input(self):
        msg = get_error_message("direct error string")
        assert msg == "direct error string"

    def test_non_string_non_exception(self):
        msg = get_error_message(None)
        assert msg == "发生未知错误"


class TestWrapError:
    def test_already_agent_toolkit_error(self):
        original = NetworkError("test")
        wrapped = wrap_error(original)
        assert wrapped is original

    def test_exception_wrapping(self):
        wrapped = wrap_error(ValueError("bad"), code="VALIDATION_ERROR")
        assert isinstance(wrapped, AgentToolkitError)
        assert wrapped.code == "VALIDATION_ERROR"
        assert isinstance(wrapped.__cause__, ValueError)

    def test_string_wrapping(self):
        wrapped = wrap_error("string error", code="STRING_ERR")
        assert isinstance(wrapped, AgentToolkitError)
        assert wrapped.args[0] == "string error"

    def test_arbitrary_object(self):
        wrapped = wrap_error(42, message="fallback")
        assert wrapped.args[0] == "fallback"
        assert wrapped.details == 42


class TestCompressError:
    def test_agent_toolkit_error(self):
        err = NetworkError("connection lost")
        compressed = compress_error(err)
        assert compressed["type"] == "NetworkError"
        assert compressed["code"] == "NETWORK_ERROR"
        assert compressed["message"] == "connection lost"

    def test_plain_exception(self):
        compressed = compress_error(ValueError("bad input"))
        assert compressed["type"] == "ValueError"
        assert "bad input" in compressed["message"]

    def test_string_input(self):
        compressed = compress_error("oops")
        assert compressed["message"] == "oops"

    def test_unknown(self):
        compressed = compress_error(42)
        assert compressed["type"] == "UnknownError"


class TestCalculateRetryDelay:
    def test_rate_limit_with_retry_after(self):
        err = RateLimitError("slow down", retry_after=5.0)
        delay = calculate_retry_delay(err, attempt=1)
        assert delay == 5.0

    def test_exponential_backoff(self):
        err = NetworkError("fail")
        assert calculate_retry_delay(err, attempt=1) == 1.0
        assert calculate_retry_delay(err, attempt=2) == 2.0
        assert calculate_retry_delay(err, attempt=3) == 4.0

    def test_exponential_backoff_capped(self):
        err = NetworkError("fail")
        delay = calculate_retry_delay(err, attempt=10, base_delay=1.0, max_delay=30.0)
        assert delay == 30.0
