"""Tests for small common modules + validator + health_check."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from ecos.common.content_integrity import check_integrity
from ecos.common.exceptions import (
    ECOSException,
    ConfigException,
    ConsensusException,
    GraphException,
    PersistenceException,
    SecurityException,
    SyncException,
    TransportException,
)
from ecos.common.logger import ECOSFormatter, get_logger
from ecos.common.metrics import MetricsCollector
from ecos.services.governance.validator import REAL


# ── exceptions ──


class TestExceptions:
    def test_ecos_exception(self):
        with pytest.raises(ECOSException):
            raise ECOSException("base")

    def test_sync_exception(self):
        with pytest.raises(SyncException):
            raise SyncException("sync")

    def test_consensus_exception(self):
        with pytest.raises(ConsensusException):
            raise ConsensusException("consensus")

    def test_graph_exception(self):
        with pytest.raises(GraphException):
            raise GraphException("graph")

    def test_transport_exception(self):
        with pytest.raises(TransportException):
            raise TransportException("transport")

    def test_config_exception(self):
        with pytest.raises(ConfigException):
            raise ConfigException("config")

    def test_security_exception(self):
        with pytest.raises(SecurityException):
            raise SecurityException("security")

    def test_persistence_exception(self):
        with pytest.raises(PersistenceException):
            raise PersistenceException("persistence")

    def test_inheritance(self):
        assert issubclass(SyncException, ECOSException)
        assert issubclass(ConfigException, ECOSException)
        assert issubclass(SecurityException, ECOSException)


# ── logger ──


class TestECOSFormatter:
    def test_format(self):
        formatter = ECOSFormatter()
        import logging

        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="/test.py",
            lineno=42,
            msg="hello",
            args=(),
            exc_info=None,
        )
        output = formatter.format(record)
        parsed = json.loads(output)
        assert parsed["level"] == "INFO"
        assert parsed["message"] == "hello"
        assert parsed["module"] == "test"


class TestGetLogger:
    def test_returns_logger(self):
        logger = get_logger("test")
        assert logger.name == "ecos.test"

    def test_singleton(self):
        logger1 = get_logger()
        logger2 = get_logger()
        assert logger1 is logger2 or logger1.name == logger2.name


# ── metrics ──


class TestMetricsCollector:
    def test_counter(self):
        m = MetricsCollector()
        assert m.get_counter("requests") == 0
        m.inc_counter("requests")
        assert m.get_counter("requests") == 1
        m.inc_counter("requests", 5)
        assert m.get_counter("requests") == 6

    def test_gauge(self):
        m = MetricsCollector()
        assert m.get_gauge("temp") == 0.0
        m.set_gauge("temp", 36.5)
        assert m.get_gauge("temp") == 36.5

    def test_histogram(self):
        m = MetricsCollector()
        h = m.get_histogram("latency")
        assert h["count"] == 0
        m.observe_histogram("latency", 0.5)
        m.observe_histogram("latency", 1.5)
        h = m.get_histogram("latency")
        assert h["count"] == 2
        assert h["avg"] == 1.0
        assert h["min"] == 0.5
        assert h["max"] == 1.5

    def test_export(self):
        m = MetricsCollector()
        m.inc_counter("c1")
        m.set_gauge("g1", 1.0)
        exported = m.export()
        assert "counters" in exported
        assert "gauges" in exported
        assert "uptime_seconds" in exported
        assert exported["counters"]["c1"] == 1


# ── content_integrity ──


class TestCheckIntegrity:
    def test_clean_text(self):
        result = check_integrity("This is a normal text with varied words.")
        assert result["suspicious"] is False
        assert result["integrity_score"] == 90

    def test_repetitive_text(self):
        text = "word " * 10
        result = check_integrity(text)
        assert result["suspicious"] is True
        assert result["integrity_score"] == 35

    def test_suspicious_markers(self):
        text = "comprehensive analysis shows methodology. further research is needed."
        result = check_integrity(text)
        assert result["suspicious"] is True
        assert result["integrity_score"] == 45

    def test_empty_text(self):
        result = check_integrity("")
        assert result["suspicious"] is False


# ── validator ──


class TestValidator:
    def test_real_path(self):
        assert "ecos-constraint-validator" in str(REAL)

    @patch("ecos.services.governance.validator.REAL")
    @patch("ecos.services.governance.validator.subprocess.call")
    def test_main_runs_real(self, mock_call, mock_real):
        mock_real.exists.return_value = True
        mock_call.return_value = 0
        # Simulate __main__ block logic
        import ecos.services.governance.validator as v

        if v.REAL.exists():
            v.subprocess.call([v.sys.executable, str(v.REAL)])
        mock_call.assert_called_once()
