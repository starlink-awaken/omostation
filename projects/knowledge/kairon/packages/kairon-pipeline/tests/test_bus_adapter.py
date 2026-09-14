"""Tests for kairon_pipeline bus_adapter (R80 backlog fix).

The bus_adapter was added in R61 as part of the cross-repo bus
adoption (Phase B migration), but it had no tests at the time.
22 months later (R80), we're adding the missing coverage so that
future changes to the adapter are guarded by regression tests.
"""
# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false

from unittest.mock import patch


class TestBusAdapter:
    def test_imports_succeed(self):
        """Adapter imports without side-effects at module load."""
        from kairon_pipeline import bus_adapter

        # The real public functions (verified by reading bus_adapter.py)
        assert hasattr(bus_adapter, "emit_source_ingested")
        assert hasattr(bus_adapter, "emit_extraction_completed")
        assert hasattr(bus_adapter, "emit_quality_gate_result")
        assert hasattr(bus_adapter, "emit_event")

    @patch("bus_foundation.facade.event.publish")
    def test_emit_source_ingested_dispatches_envelope(self, mock_publish):
        """emit_source_ingested() should call publish() with a
        properly-shaped BusEnvelope."""
        from kairon_pipeline import bus_adapter

        result = bus_adapter.emit_source_ingested(
            source_name="gdelt",
            record_count=1234,
        )
        mock_publish.assert_called_once()
        kwargs = mock_publish.call_args[1]
        assert kwargs["topic"] == "kairon:source:ingested"
        assert "bos://capability/pipeline/" in kwargs["source_uri"]
        assert kwargs["payload"]["source"] == "gdelt"
        assert kwargs["payload"]["record_count"] == 1234
        assert result == "kairon:source:ingested"

    @patch("bus_foundation.facade.event.publish")
    def test_emit_extraction_completed_dispatches_envelope(self, mock_publish):
        """emit_extraction_completed() should call publish()."""
        from kairon_pipeline import bus_adapter

        bus_adapter.emit_extraction_completed(
            pipeline_id="harvest-2026-06-13",
            extractor="html-clean",
            duration_ms=12500,
        )
        mock_publish.assert_called_once()
        kwargs = mock_publish.call_args[1]
        assert kwargs["topic"] == "kairon:extraction:completed"
        assert kwargs["payload"]["extractor"] == "html-clean"
        assert kwargs["payload"]["duration_ms"] == 12500

    @patch("bus_foundation.facade.event.publish")
    def test_emit_quality_gate_result_passed(self, mock_publish):
        """When a quality gate passes, the envelope payload says so."""
        from kairon_pipeline import bus_adapter

        bus_adapter.emit_quality_gate_result(
            pipeline_id="harvest-2026-06-13",
            gate="quality",
            passed=True,
        )
        mock_publish.assert_called_once()
        kwargs = mock_publish.call_args[1]
        assert kwargs["topic"] == "kairon:quality_gate:result"
        assert kwargs["payload"]["passed"] is True

    @patch("bus_foundation.facade.event.publish")
    def test_emit_quality_gate_result_records_rejection(self, mock_publish):
        """When a quality gate fails, the rejection reason is in payload."""
        from kairon_pipeline import bus_adapter

        bus_adapter.emit_quality_gate_result(
            pipeline_id="harvest-fail",
            gate="quality",
            passed=False,
            rejection_reason="3 records below threshold",
        )
        kwargs = mock_publish.call_args[1]
        assert kwargs["payload"]["passed"] is False
        assert kwargs["payload"]["rejection_reason"] == "3 records below threshold"

    @patch("bus_foundation.facade.event.publish", side_effect=ConnectionError("agora unreachable"))
    def test_publish_failure_does_not_propagate(self, mock_publish):
        """If publish() raises (e.g., agora.bus unavailable), the
        adapter should NOT propagate the exception — it should
        log and continue. Pipeline must not abort on bus failure."""
        from kairon_pipeline import bus_adapter

        # Should not raise — the adapter is intentionally
        # besteffort: the pipeline is the source of truth, the
        # bus is a notification channel.
        bus_adapter.emit_source_ingested(
            source_name="gdelt",
            record_count=0,
        )
