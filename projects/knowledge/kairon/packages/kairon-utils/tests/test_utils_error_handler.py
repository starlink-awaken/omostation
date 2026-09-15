"""Tests for kairon_lib.utils.error_handler — ErrorHandler, ErrorContext, handle_exception."""
# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false

import pytest
from kairon_utils.error_classifier import ErrorCategory
from kairon_utils.error_handler import ErrorContext, ErrorHandler, create_error_handler, handle_exception


class TestErrorHandler:
    def test_handle_error_default(self):
        handler = ErrorHandler("test-component")
        result = handler.handle_error(ValueError("bad"))
        assert result["category"] == ErrorCategory.VALIDATION_ERROR
        assert result["retryable"] is False
        assert "Fix input" in result["action"]  # type: ignore[reportOperatorIssue]

    def test_handle_error_with_source(self):
        handler = ErrorHandler("test-component")
        result = handler.handle_error(TimeoutError("timeout"), source_id="src1")
        assert result["retryable"] is True
        assert "source_id" in result["context"]  # type: ignore[reportOperatorIssue]

    def test_handle_error_with_context(self):
        handler = ErrorHandler("test-component")
        result = handler.handle_error(RuntimeError("fail"), context={"extra": "info"})
        assert result["context"]["extra"] == "info"  # type: ignore[reportIndexIssue]

    def test_error_counts(self):
        handler = ErrorHandler("test")
        handler.handle_error(TimeoutError("t1"))
        handler.handle_error(TimeoutError("t2"))
        handler.handle_error(ValueError("v"))
        stats = handler.get_error_statistics()
        assert stats["transient"] == 2
        assert stats["validation"] == 1

    def test_reset_error_statistics(self):
        handler = ErrorHandler("test")
        handler.handle_error(ValueError("v"))
        handler.reset_error_statistics()
        stats = handler.get_error_statistics()
        assert all(v == 0 for v in stats.values())

    def test_log_harvest_start(self):
        handler = ErrorHandler("test")
        handler.log_harvest_start("src1")  # should not raise

    def test_log_harvest_success(self):
        handler = ErrorHandler("test")
        handler.log_harvest_success("src1", 10, 100.0)  # should not raise

    def test_log_harvest_failure(self):
        handler = ErrorHandler("test")
        handler.log_harvest_failure("src1", ValueError("msg"))  # should not raise

    def test_log_quality_gate_rejection(self):
        handler = ErrorHandler("test")
        handler.log_quality_gate_rejection("src1", 0.5, "low score")  # should not raise

    def test_log_checkpoint_saved(self):
        handler = ErrorHandler("test")
        handler.log_checkpoint_saved("src1", "step1")  # should not raise

    def test_log_rate_limit_exceeded(self):
        handler = ErrorHandler("test")
        handler.log_rate_limit_exceeded("src1")  # should not raise
        handler.log_rate_limit_exceeded("src1", retry_after=30)  # should not raise

    def test_handle_exception_function(self):
        result = handle_exception(ConnectionError("refused"), "test")
        assert result["category"] == ErrorCategory.TRANSIENT
        assert result["retryable"] is True

    def test_create_error_handler(self):
        handler = create_error_handler("test")
        assert isinstance(handler, ErrorHandler)
        assert handler.component_name == "test"


class TestErrorContext:
    def test_context_suppresses_error(self):
        with ErrorContext("test") as ctx:
            raise ValueError("expected error")
        assert ctx.error_occurred is True
        assert ctx.error_result is not None
        assert ctx.error_result["category"] == ErrorCategory.VALIDATION_ERROR

    def test_context_reraises_error(self):
        with pytest.raises(ValueError):
            with ErrorContext("test", reraise=True):
                raise ValueError("should propagate")

    def test_context_no_error(self):
        with ErrorContext("test") as ctx:
            pass
        assert ctx.error_occurred is False
        assert ctx.error_result is None

    def test_context_with_source_and_context(self):
        with ErrorContext("test", context={"key": "val"}, source_id="src1") as ctx:
            raise KeyError("missing")
        assert ctx.error_occurred is True
        assert ctx.error_result["category"] == ErrorCategory.VALIDATION_ERROR  # type: ignore[reportOptionalSubscript]

    def test_get_error_result(self):
        with ErrorContext("test") as ctx:
            raise RuntimeError("fail")
        result = ctx.get_error_result()
        assert result is not None
        assert "category" in result
