"""Tests for eidos.logging."""
# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false

import json
import logging


class TestStructuredFormatter:
    """Test StructuredFormatter class."""

    def test_import(self):
        from eidos.logging import StructuredFormatter

        assert StructuredFormatter is not None

    def test_format_basic_record(self):
        from eidos.logging import StructuredFormatter

        formatter = StructuredFormatter()
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname=__file__,
            lineno=42,
            msg="test message",
            args=(),
            exc_info=None,
        )
        output = formatter.format(record)
        parsed = json.loads(output)

        assert parsed["level"] == "INFO"
        assert parsed["logger"] == "test_logger"
        assert parsed["message"] == "test message"
        assert "timestamp" in parsed

    def test_format_with_structured_data(self):
        from eidos.logging import StructuredFormatter

        formatter = StructuredFormatter()
        record = logging.LogRecord(
            name="test_logger",
            level=logging.WARNING,
            pathname=__file__,
            lineno=42,
            msg="validation failed",
            args=(),
            exc_info=None,
        )
        record.structured = {"file": "data.json", "errors": 3}
        output = formatter.format(record)
        parsed = json.loads(output)

        assert parsed["message"] == "validation failed"
        assert parsed["file"] == "data.json"
        assert parsed["errors"] == 3

    def test_format_json_serializable(self):
        from eidos.logging import StructuredFormatter

        formatter = StructuredFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname=__file__,
            lineno=42,
            msg="error with 中文",
            args=(),
            exc_info=None,
        )
        output = formatter.format(record)
        parsed = json.loads(output)

        assert parsed["message"] == "error with 中文"


class TestLogger:
    """Test module-level logger."""

    def test_logger_exists(self):
        from eidos.logging import logger

        assert logger is not None
        assert logger.name == "eidos"
        assert logger.level >= logging.INFO

    def test_log_info(self, caplog):
        from eidos.logging import logger

        with caplog.at_level(logging.INFO):
            logger.info("hello eidos")
            assert "hello eidos" in caplog.text

    def test_log_warning(self, caplog):
        from eidos.logging import logger

        with caplog.at_level(logging.WARNING):
            logger.warning("warning message")
            assert "warning message" in caplog.text
