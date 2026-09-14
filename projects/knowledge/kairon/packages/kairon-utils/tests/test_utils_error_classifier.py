"""Tests for kairon_lib.utils.error_classifier — ErrorCategory, ErrorClassifier, ErrorStatistics."""
# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false

from kairon_utils.error_classifier import ErrorCategory, ErrorClassifier, ErrorStatistics


class TestErrorCategory:
    def test_values(self):
        assert ErrorCategory.TRANSIENT.value == "transient"
        assert ErrorCategory.PERMANENT.value == "permanent"
        assert ErrorCategory.RATE_LIMIT.value == "rate_limit"
        assert ErrorCategory.AUTH_FAILURE.value == "auth"
        assert ErrorCategory.VALIDATION_ERROR.value == "validation"
        assert ErrorCategory.SYSTEM_ERROR.value == "system"


class TestErrorClassifier:
    def test_classify_timeout(self):
        c = ErrorClassifier()
        assert c.classify(TimeoutError("timeout")) == ErrorCategory.TRANSIENT

    def test_classify_connection_error(self):
        c = ErrorClassifier()
        assert c.classify(ConnectionError("refused")) == ErrorCategory.TRANSIENT

    def test_classify_permission_error(self):
        c = ErrorClassifier()
        assert c.classify(PermissionError("denied")) == ErrorCategory.AUTH_FAILURE

    def test_classify_value_error(self):
        c = ErrorClassifier()
        assert c.classify(ValueError("bad value")) == ErrorCategory.VALIDATION_ERROR

    def test_classify_key_error(self):
        c = ErrorClassifier()
        assert c.classify(KeyError("missing")) == ErrorCategory.VALIDATION_ERROR

    def test_classify_os_error(self):
        c = ErrorClassifier()
        assert c.classify(OSError("disk full")) == ErrorCategory.SYSTEM_ERROR

    def test_classify_unknown_error_defaults_to_system(self):
        c = ErrorClassifier()
        assert c.classify(RuntimeError("weird")) == ErrorCategory.SYSTEM_ERROR

    def test_classify_asyncio_timeout(self):
        c = ErrorClassifier()
        assert c.classify(TimeoutError()) == ErrorCategory.TRANSIENT

    def test_classify_http_status_429(self):
        c = ErrorClassifier()
        error = RuntimeError("rate limited")
        error.status = 429  # type: ignore[attr-defined]
        assert c.classify(error) == ErrorCategory.RATE_LIMIT

    def test_classify_http_status_4xx(self):
        c = ErrorClassifier()
        error = RuntimeError("not found")
        error.status = 404  # type: ignore[attr-defined]
        assert c.classify(error) == ErrorCategory.PERMANENT

    def test_classify_http_status_5xx(self):
        c = ErrorClassifier()
        error = RuntimeError("server error")
        error.status = 503  # type: ignore[attr-defined]
        assert c.classify(error) == ErrorCategory.TRANSIENT

    def test_classify_http_status_2xx(self):
        """2xx status codes fall through to default."""
        c = ErrorClassifier()
        error = RuntimeError("ok?")
        error.status = 200  # type: ignore[attr-defined]
        # status 200 doesn't match any HTTP branch, falls to default SYSTEM_ERROR
        assert c.classify(error) == ErrorCategory.SYSTEM_ERROR

    def test_get_recovery_action(self):
        c = ErrorClassifier()
        assert "exponential backoff" in c.get_recovery_action(ErrorCategory.TRANSIENT)
        assert "manual intervention" in c.get_recovery_action(ErrorCategory.PERMANENT)
        assert "Back off" in c.get_recovery_action(ErrorCategory.RATE_LIMIT)
        assert "Refresh credentials" in c.get_recovery_action(ErrorCategory.AUTH_FAILURE)
        assert "Fix input" in c.get_recovery_action(ErrorCategory.VALIDATION_ERROR)
        assert "Alert operations" in c.get_recovery_action(ErrorCategory.SYSTEM_ERROR)

    def test_should_retry(self):
        c = ErrorClassifier()
        assert c.should_retry(ErrorCategory.TRANSIENT) is True
        assert c.should_retry(ErrorCategory.RATE_LIMIT) is True
        assert c.should_retry(ErrorCategory.AUTH_FAILURE) is True
        assert c.should_retry(ErrorCategory.PERMANENT) is False
        assert c.should_retry(ErrorCategory.VALIDATION_ERROR) is False
        assert c.should_retry(ErrorCategory.SYSTEM_ERROR) is False

    def test_classify_with_context(self):
        c = ErrorClassifier()
        result = c.classify_with_context(TimeoutError("msg"), "src1")
        assert result["category"] == "transient"
        assert result["retryable"] is True
        assert result["source_id"] == "src1"
        assert result["error_type"] == "TimeoutError"
        assert result["error_message"] == "msg"

    def test_log_error_does_not_raise(self):
        """log_error should be callable without raising."""
        c = ErrorClassifier()
        c.log_error(ValueError("test"), "src1")  # should not raise


class TestErrorStatistics:
    def test_initial_state(self):
        s = ErrorStatistics()
        assert s.get_statistics("src1") == {}

    def test_record_and_get(self):
        s = ErrorStatistics()
        s.record_error("src1", ErrorCategory.TRANSIENT)
        s.record_error("src1", ErrorCategory.TRANSIENT)
        s.record_error("src1", ErrorCategory.PERMANENT)
        stats = s.get_statistics("src1")
        assert stats["transient"] == 2
        assert stats["permanent"] == 1

    def test_multiple_sources(self):
        s = ErrorStatistics()
        s.record_error("src1", ErrorCategory.TRANSIENT)
        s.record_error("src2", ErrorCategory.PERMANENT)
        assert s.get_statistics("src1")["transient"] == 1
        assert s.get_statistics("src2")["permanent"] == 1

    def test_reset_statistics(self):
        s = ErrorStatistics()
        s.record_error("src1", ErrorCategory.TRANSIENT)
        s.reset_statistics("src1")
        assert s.get_statistics("src1") == {}

    def test_reset_nonexistent_source(self):
        s = ErrorStatistics()
        s.reset_statistics("nonexistent")  # should not raise
