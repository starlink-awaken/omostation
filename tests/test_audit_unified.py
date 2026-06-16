"""Tests for Audit Unified — the unified audit layer."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch


from ecos.services.governance.audit_unified import (
    REQUIRED_FIELDS,
    _append_jsonl,
    _format_event,
    _generate_id,
    _parse_dt,
    _query_jsonl,
    create_audit_debt,
    log_event,
    print_audit_report,
    query_events,
)


class TestGenerateId:
    def test_returns_string(self):
        eid = _generate_id()
        assert eid.startswith("unified-")
        assert len(eid) > 20


class TestFormatEvent:
    def test_sets_defaults(self):
        event = _format_event({"source": "l0", "event_type": "test", "summary": "x"})
        assert "id" in event
        assert "timestamp" in event
        assert event["source"] == "l0"

    def test_fills_missing_required_fields(self):
        event = _format_event({})
        for f in REQUIRED_FIELDS:
            assert f in event


class TestParseDt:
    def test_parse_iso(self):
        dt = _parse_dt("2026-06-16T10:00:00")
        assert dt is not None
        assert dt.year == 2026

    def test_parse_with_tz(self):
        dt = _parse_dt("2026-06-16T10:00:00+08:00")
        assert dt is not None
        assert dt.tzinfo is None  # normalized to naive

    def test_parse_invalid(self):
        assert _parse_dt("not-a-date") is None

    def test_parse_none(self):
        assert _parse_dt(None) is None  # type: ignore[arg-type]


class TestAppendJsonl:
    @patch("ecos.services.governance.audit_unified.Path.mkdir")
    def test_appends_line(self, mock_mkdir):
        with patch("ecos.services.governance.audit_unified.open", mock_open()) as m:
            _append_jsonl(Path("/fake/log.jsonl"), {"key": "value"})
            handle = m()
            written = handle.write.call_args[0][0]
            assert "key" in written
            assert "value" in written

    @patch("ecos.services.governance.audit_unified.Path.mkdir")
    def test_silent_on_error(self, mock_mkdir):
        mock_mkdir.side_effect = PermissionError("denied")
        _append_jsonl(Path("/fake/log.jsonl"), {"key": "value"})  # should not raise


class TestLogEvent:
    @patch("ecos.services.governance.audit_unified._ssb_publish")
    @patch("ecos.services.governance.audit_unified._append_jsonl")
    def test_minimal_event(self, mock_append, mock_ssb):
        mock_ssb.return_value = None
        event = log_event(source="l0", event_type="test", summary="hello")
        assert event["source"] == "l0"
        assert event["event_type"] == "test"
        assert event["summary"] == "hello"
        assert mock_append.call_count >= 2  # l0 + unified

    @patch("ecos.services.governance.audit_unified._ssb_publish")
    @patch("ecos.services.governance.audit_unified._append_jsonl")
    def test_full_event(self, mock_append, mock_ssb):
        mock_ssb.return_value = "ssb-event-123"
        event = log_event(
            source="bos",
            event_type="bos_call",
            summary="test",
            detail="detail text",
            uri="bos://test/resource",
            domain="test",
            passed=False,
            violations=[{"id": "X4-C05"}],
            cards_id="CARDS-001",
            daemon_cycle_id=42,
            healer_check_type="port",
            duration_ms=150,
            anomaly=True,
            metadata={"extra": "info"},
        )
        assert event["uri"] == "bos://test/resource"
        assert event["passed"] is False
        assert event["violations"] == [{"id": "X4-C05"}]
        assert event["ssb_event_id"] == "ssb-event-123"
        assert event["anomaly"] is True

    @patch("ecos.services.governance.audit_unified._ssb_publish")
    @patch("ecos.services.governance.audit_unified._append_jsonl")
    def test_summary_truncated(self, mock_append, mock_ssb):
        long_summary = "x" * 500
        event = log_event(source="l0", event_type="test", summary=long_summary)
        assert len(event["summary"]) <= 200

    @patch("ecos.services.governance.audit_unified._ssb_publish")
    @patch("ecos.services.governance.audit_unified._append_jsonl")
    def test_detail_truncated(self, mock_append, mock_ssb):
        long_detail = "x" * 2000
        event = log_event(source="l0", event_type="test", detail=long_detail)
        assert len(event["detail"]) <= 1000


class TestQueryJsonl:
    @patch("ecos.services.governance.audit_unified.Path.exists")
    def test_file_not_exists(self, mock_exists):
        mock_exists.return_value = False
        assert _query_jsonl(Path("/fake.jsonl")) == []

    @patch("ecos.services.governance.audit_unified.Path.exists")
    def test_reads_events(self, mock_exists):
        mock_exists.return_value = True
        now = datetime.now()
        lines = [
            json.dumps({"timestamp": now.isoformat(), "source": "l0", "event_type": "read"}),
            json.dumps({"timestamp": (now - timedelta(hours=2)).isoformat(), "source": "l0", "event_type": "write"}),
        ]
        with patch("ecos.services.governance.audit_unified.open", mock_open(read_data="\n".join(lines))):
            events = _query_jsonl(Path("/fake.jsonl"), hours=24)
            assert len(events) == 2

    @patch("ecos.services.governance.audit_unified.Path.exists")
    def test_filters_by_source(self, mock_exists):
        mock_exists.return_value = True
        now = datetime.now()
        lines = [
            json.dumps({"timestamp": now.isoformat(), "source": "l0"}),
            json.dumps({"timestamp": now.isoformat(), "source": "bos"}),
        ]
        with patch("ecos.services.governance.audit_unified.open", mock_open(read_data="\n".join(lines))):
            events = _query_jsonl(Path("/fake.jsonl"), hours=24, source_filter="l0")
            assert len(events) == 1
            assert events[0]["source"] == "l0"

    @patch("ecos.services.governance.audit_unified.Path.exists")
    def test_filters_by_time(self, mock_exists):
        mock_exists.return_value = True
        now = datetime.now()
        lines = [
            json.dumps({"timestamp": now.isoformat(), "source": "l0"}),
            json.dumps({"timestamp": (now - timedelta(hours=48)).isoformat(), "source": "l0"}),
        ]
        with patch("ecos.services.governance.audit_unified.open", mock_open(read_data="\n".join(lines))):
            events = _query_jsonl(Path("/fake.jsonl"), hours=24)
            assert len(events) == 1

    @patch("ecos.services.governance.audit_unified.Path.exists")
    def test_skips_bad_lines(self, mock_exists):
        mock_exists.return_value = True
        lines = ["not json", json.dumps({"timestamp": datetime.now().isoformat(), "source": "l0"})]
        with patch("ecos.services.governance.audit_unified.open", mock_open(read_data="\n".join(lines))):
            events = _query_jsonl(Path("/fake.jsonl"), hours=24)
            assert len(events) == 1


class TestCreateAuditDebt:
    @patch("ecos.services.governance.audit_unified.Path.exists")
    def test_db_not_exists(self, mock_exists):
        mock_exists.return_value = False
        result = create_audit_debt("bos://test", "violation", "details")
        assert result is None

    @patch("ecos.services.governance.audit_unified.Path.exists")
    @patch("ecos.services.governance.audit_unified.sqlite3.connect")
    def test_creates_debt_card(self, mock_connect, mock_exists):
        mock_exists.return_value = True
        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchone.return_value = None
        mock_connect.return_value = mock_conn

        result = create_audit_debt("bos://test/resource", "violation", "details")
        assert result is not None
        assert "DEBT-AUDIT" in result

    @patch("ecos.services.governance.audit_unified.Path.exists")
    @patch("ecos.services.governance.audit_unified.sqlite3.connect")
    def test_skips_existing_debt(self, mock_connect, mock_exists):
        mock_exists.return_value = True
        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchone.return_value = ("DEBT-AUDIT-xxx",)
        mock_connect.return_value = mock_conn

        result = create_audit_debt("bos://test", "violation", "details")
        assert result is not None  # returns existing id

    @patch("ecos.services.governance.audit_unified.Path.exists")
    def test_silent_on_error(self, mock_exists):
        mock_exists.side_effect = PermissionError("denied")
        result = create_audit_debt("bos://test", "violation", "details")
        assert result is None


class TestQueryEvents:
    @patch("ecos.services.governance.audit_unified._query_jsonl")
    @patch("ecos.services.governance.audit_unified._query_ssb")
    @patch("ecos.services.governance.audit_unified._query_daemon_db")
    @patch("ecos.services.governance.audit_unified._query_healer_db")
    def test_query_all_sources(self, mock_healer, mock_daemon, mock_ssb, mock_jsonl):
        mock_jsonl.return_value = []
        mock_ssb.return_value = []
        mock_daemon.return_value = []
        mock_healer.return_value = []
        result = query_events(hours=24, source="all")
        assert result["total"] == 0
        assert "l0" in result["sources"]
        assert "bos" in result["sources"]
        assert "ssb" in result["sources"]

    @patch("ecos.services.governance.audit_unified._query_jsonl")
    def test_query_single_source(self, mock_jsonl):
        mock_jsonl.return_value = [
            {"timestamp": datetime.now().isoformat(), "source": "l0", "event_type": "read", "passed": True}
        ]
        result = query_events(hours=24, source="l0")
        assert result["total"] == 1
        assert result["passed"] == 1

    @patch("ecos.services.governance.audit_unified._query_jsonl")
    def test_query_filters_domain(self, mock_jsonl):
        mock_jsonl.return_value = [
            {"timestamp": datetime.now().isoformat(), "source": "l0", "event_type": "read", "domain": "a"},
            {"timestamp": datetime.now().isoformat(), "source": "l0", "event_type": "read", "domain": "b"},
        ]
        result = query_events(hours=24, source="l0", domain="a")
        assert result["total"] == 1

    @patch("ecos.services.governance.audit_unified._query_jsonl")
    def test_query_counts_passed_failed(self, mock_jsonl):
        mock_jsonl.return_value = [
            {"timestamp": datetime.now().isoformat(), "source": "l0", "event_type": "read", "passed": True},
            {"timestamp": datetime.now().isoformat(), "source": "l0", "event_type": "write", "passed": False},
            {"timestamp": datetime.now().isoformat(), "source": "l0", "event_type": "delete", "passed": True},
        ]
        result = query_events(hours=24, source="l0")
        assert result["passed"] == 2
        assert result["failed"] == 1

    @patch("ecos.services.governance.audit_unified._query_jsonl")
    def test_query_respects_limit(self, mock_jsonl):
        events = [
            {"timestamp": datetime.now().isoformat(), "source": "l0", "event_type": f"e{i}", "passed": True}
            for i in range(50)
        ]
        mock_jsonl.return_value = events
        result = query_events(hours=24, source="l0", limit=10)
        assert result["total"] == 10


class TestPrintAuditReport:
    def test_empty_report(self, capsys):
        print_audit_report({"sources": {}, "total": 0, "passed": 0, "failed": 0, "anomalies": 0, "events": []})
        captured = capsys.readouterr()
        assert "无审计事件" in captured.out

    def test_with_events(self, capsys):
        print_audit_report({
            "sources": {"l0": 2, "bos": 1},
            "total": 3,
            "passed": 2,
            "failed": 1,
            "anomalies": 0,
            "events": [
                {"timestamp": "2026-06-16T10:00:00", "source": "l0", "event_type": "read", "passed": True, "summary": "ok"},
                {"timestamp": "2026-06-16T11:00:00", "source": "bos", "event_type": "write", "passed": False, "summary": "fail"},
            ],
        })
        captured = capsys.readouterr()
        assert "l0=2" in captured.out
        assert "✅" in captured.out
        assert "❌" in captured.out
