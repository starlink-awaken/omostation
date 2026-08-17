"""Tests for kairon_lib.utils.logging — JSONFormatter, StructuredLogger, get_logger."""
# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false

import json
import logging
import tempfile
from pathlib import Path

import pytest
from kairon_utils.logging import JSONFormatter, StructuredLogger, get_logger


class TestJSONFormatter:
    def test_format_includes_required_fields(self):
        fmt = JSONFormatter(component="test-comp")
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="/test/path.py",
            lineno=42,
            msg="hello world",
            args=(),
            exc_info=None,
        )
        output = fmt.format(record)
        data = json.loads(output)
        assert data["level"] == "INFO"
        assert data["component"] == "test-comp"
        assert data["logger"] == "test_logger"
        assert data["message"] == "hello world"
        assert data["module"] == "path"
        # funcName may be None or a string depending on Python version
        assert data["function"] is None or isinstance(data["function"], str)
        assert data["line"] == 42
        assert "timestamp" in data

    def test_format_with_context(self):
        fmt = JSONFormatter()
        record = logging.LogRecord("logger", logging.WARNING, "/f.py", 10, "msg", (), None)
        record.context = {"key": "val"}  # type: ignore[attr-defined]
        output = fmt.format(record)
        data = json.loads(output)
        assert data["context"] == {"key": "val"}

    def test_default_component(self):
        fmt = JSONFormatter()
        record = logging.LogRecord("logger", logging.DEBUG, "/f.py", 1, "msg", (), None)
        data = json.loads(fmt.format(record))
        assert data["component"] == "kairon"


class TestStructuredLogger:
    @pytest.fixture
    def tmp_log(self):
        with tempfile.TemporaryDirectory() as d:
            yield Path(d) / "test.log"

    def test_logger_creation(self, tmp_log):
        logger = StructuredLogger("test-module", component="test-comp", log_file=tmp_log)
        assert logger._logger.name == "test-module"
        assert logger._logger.level == logging.DEBUG

    def test_info_log(self, tmp_log):
        logger = StructuredLogger("test-module", log_file=tmp_log)
        logger.info("info message")
        log_content = tmp_log.read_text()
        assert "info message" in log_content

    def test_debug_log(self, tmp_log):
        logger = StructuredLogger("test-module", log_file=tmp_log)
        logger.debug("debug message")
        log_content = tmp_log.read_text()
        assert "debug message" in log_content

    def test_warning_log(self, tmp_log):
        logger = StructuredLogger("test-module", log_file=tmp_log)
        logger.warning("warning message")
        log_content = tmp_log.read_text()
        assert "warning message" in log_content

    def test_error_log(self, tmp_log):
        logger = StructuredLogger("test-module", log_file=tmp_log)
        logger.error("error message")
        log_content = tmp_log.read_text()
        assert "error message" in log_content

    def test_critical_log(self, tmp_log):
        logger = StructuredLogger("test-module", log_file=tmp_log)
        logger.critical("critical message")
        log_content = tmp_log.read_text()
        assert "critical message" in log_content

    def test_log_with_context(self, tmp_log):
        logger = StructuredLogger("test-module", log_file=tmp_log)
        logger.info("context test", context={"req_id": "abc"})
        log_content = tmp_log.read_text()
        data = json.loads(log_content.strip().split("\n")[0])
        assert data["context"] == {"req_id": "abc"}

    def test_error_with_exc_info(self, tmp_log):
        logger = StructuredLogger("test-module", log_file=tmp_log)
        try:
            raise ValueError("test error")
        except ValueError:
            logger.error("error occurred", exc_info=True)
        log_content = tmp_log.read_text()
        data = json.loads(log_content.strip().split("\n")[0])
        assert data["message"] == "error occurred"
        assert "exception" in data

    def test_critical_with_exc_info(self, tmp_log):
        logger = StructuredLogger("test-module", log_file=tmp_log)
        try:
            raise RuntimeError("critical error")
        except RuntimeError:
            logger.critical("critical occurred", exc_info=True)
        log_content = tmp_log.read_text()
        data = json.loads(log_content.strip().split("\n")[0])
        assert data["message"] == "critical occurred"
        assert "exception" in data

    def test_json_formatted_output(self, tmp_log):
        logger = StructuredLogger("test-module", log_file=tmp_log)
        logger.info("json test")
        log_content = tmp_log.read_text()
        # Each line should be valid JSON
        for line in log_content.strip().split("\n"):
            data = json.loads(line)
            assert "timestamp" in data
            assert "level" in data
            assert "message" in data

    @pytest.fixture
    def logger_no_file(self):
        # No file handler, just console
        return StructuredLogger("no-file-logger")

    def test_no_file_logger_does_not_crash(self, logger_no_file):
        logger_no_file.info("no file test")  # should not raise

    def test_get_logger(self, tmp_log):
        logger = get_logger("test-module", component="test-comp", log_file=tmp_log)
        assert isinstance(logger, StructuredLogger)
        logger.info("via get_logger")
        assert tmp_log.exists()
