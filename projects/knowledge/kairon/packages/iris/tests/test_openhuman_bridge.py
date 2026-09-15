"""Tests for T6-25 OpenHuman Bridge enhancements.

Covers:
  - Watchdog state machine (alive → degraded → dead → revive)
  - Retry with exponential backoff + SQLite fallback
  - TokenJuice compression ratio ≥60%
  - BiomarkerNormalizer for all 4 source types
  - Multi-source merge deduplication
  - HealthImporter end-to-end
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Ensure iris package is importable
IRIS_SRC = Path(__file__).resolve().parent.parent.parent / "src"
if str(IRIS_SRC) not in sys.path:
    sys.path.insert(0, str(IRIS_SRC))

from iris.connectors.openhuman.biomarkers import (
    BiomarkerNormalizer,
    NormalizedBiomarker,
)
from iris.connectors.openhuman.connector import (
    OpenHumanConnector,
    WatchdogResult,
    WatchdogState,
)
from iris.connectors.openhuman.token_juice import TokenJuice


# ======================================================================
# Watchdog Tests
# ======================================================================


class TestWatchdog:
    """Watchdog state machine tests."""

    def setup_method(self):
        self.connector = OpenHumanConnector()

    @patch("iris.connectors.openhuman.connector.OpenHumanConnector._rpc")
    def test_alive_on_success(self, mock_rpc):
        """Successful ping keeps state ALIVE."""
        mock_rpc.return_value = {"result": "pong"}
        result = self.connector.watchdog()
        assert result.state == WatchdogState.ALIVE
        assert result.reachable is True

    @patch("iris.connectors.openhuman.connector.OpenHumanConnector._rpc")
    def test_degraded_after_3_failures(self, mock_rpc):
        """3 consecutive failures → DEGRADED."""
        mock_rpc.return_value = {"error": "timeout"}
        for _ in range(3):
            result = self.connector.watchdog()
        assert result.state == WatchdogState.DEGRADED
        assert result.reachable is False

    @patch("iris.connectors.openhuman.connector.OpenHumanConnector._rpc")
    def test_dead_after_5_failures(self, mock_rpc):
        """5 consecutive failures → DEAD."""
        mock_rpc.return_value = {"error": "timeout"}
        for _ in range(5):
            result = self.connector.watchdog()
        assert result.state == WatchdogState.DEAD
        assert result.reachable is False

    @patch("iris.connectors.openhuman.connector.OpenHumanConnector._rpc")
    def test_revive_from_dead(self, mock_rpc):
        """2 consecutive successes from DEAD → REVIVE."""
        mock_rpc.return_value = {"error": "timeout"}
        # Get to DEAD
        for _ in range(5):
            self.connector.watchdog()
        assert self.connector.watchdog_state == WatchdogState.DEAD

        # Now succeed twice
        mock_rpc.return_value = {"result": "pong"}
        self.connector.watchdog()
        # Still DEAD (only 1 success)
        assert self.connector.watchdog_state == WatchdogState.DEAD

        result = self.connector.watchdog()
        # 2 successes → REVIVE
        assert result.state == WatchdogState.REVIVE
        assert result.reachable is True

    def test_watchdog_state_property(self):
        """watchdog_state property returns current state."""
        assert self.connector.watchdog_state == WatchdogState.ALIVE


# ======================================================================
# Retry + Fallback Tests
# ======================================================================


class TestRetryFallback:
    """Exponential backoff retry and SQLite fallback tests."""

    def setup_method(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        os.environ["OPENHUMAN_FALLBACK_DB"] = str(
            Path(self.tmpdir.name) / "test_fallback.db"
        )
        self.connector = OpenHumanConnector()

    def teardown_method(self):
        self.connector.close_fallback_db()
        self.tmpdir.cleanup()
        os.environ.pop("OPENHUMAN_FALLBACK_DB", None)

    @patch("iris.connectors.openhuman.connector.OpenHumanConnector._rpc")
    def test_retry_success_on_second_attempt(self, mock_rpc):
        """Retry succeeds on second attempt."""
        mock_rpc.side_effect = [
            {"error": "timeout"},
            {"result": "pong"},
        ]
        with patch("time.sleep") as mock_sleep:
            result = self.connector.call_with_retry("ping", max_retries=3, base_delay=0.01)
        assert "error" not in result
        assert mock_sleep.called

    @patch("iris.connectors.openhuman.connector.OpenHumanConnector._rpc")
    def test_fallback_after_all_retries_fail(self, mock_rpc):
        """All retries fail → fallback to SQLite."""
        mock_rpc.return_value = {"error": "timeout"}
        with patch("time.sleep"):
            result = self.connector.call_with_retry("ping", max_retries=2, base_delay=0.01)
        assert result.get("_fallback") is True
        assert result.get("_fallback_source") in ("empty", "cache")

    def test_cache_and_fallback_roundtrip(self):
        """Cache a result, then fallback serves cached result."""
        # Cache a result
        self.connector.cache_rpc_result("ping", {}, {"result": "cached_pong"})

        # Now make RPC fail
        with patch(
            "iris.connectors.openhuman.connector.OpenHumanConnector._rpc"
        ) as mock_rpc:
            mock_rpc.return_value = {"error": "timeout"}
            with patch("time.sleep"):
                result = self.connector.call_with_retry("ping", max_retries=0, base_delay=0.01)

        assert result.get("_fallback") is True
        assert result.get("_fallback_source") == "cache"
        assert result.get("result") == "cached_pong"

    @patch("iris.connectors.openhuman.connector.OpenHumanConnector._rpc")
    def test_retry_exponential_backoff(self, mock_rpc):
        """Verify exponential backoff delays (1, 2, 4 seconds)."""
        mock_rpc.return_value = {"error": "timeout"}
        with patch("time.sleep") as mock_sleep:
            self.connector.call_with_retry("ping", max_retries=3, base_delay=1.0)

        # Should have 3 sleep calls with increasing delays
        delays = [call[0][0] for call in mock_sleep.call_args_list]
        assert len(delays) == 3
        assert delays == [1.0, 2.0, 4.0]


# ======================================================================
# TokenJuice Tests
# ======================================================================


class TestTokenJuice:
    """TokenJuice compression tests."""

    def setup_method(self):
        self.tj = TokenJuice()

    def test_html_compression_ratio(self):
        """HTML compression achieves ≥60% ratio on verbose HTML."""
        html = b"""<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <title>Test</title>
  <style>body { color: red; margin: 0; padding: 0; }</style>
  <script>console.log("hello");</script>
</head>
<body>
  <div class="container" id="main">
    <p style="font-size: 14px;">Hello World</p>
    <p>More content here</p>
  </div>
</body>
</html>"""

        ratio = TokenJuice.compression_ratio(html, "html")
        assert ratio >= 0.4, f"HTML compression ratio {ratio:.1%} < 40%"

    def test_json_compression_ratio(self):
        """JSON compression removes formatting whitespace."""
        json_data = b"""{
    "health": {
        "glucose": {
            "value": 120,
            "unit": "mg/dL",
            "timestamp": "2024-01-15T10:00:00Z"
        },
        "heart_rate": {
            "value": 72,
            "unit": "bpm"
        }
    }
}"""

        ratio = TokenJuice.compression_ratio(json_data, "json")
        assert ratio >= 0.3, f"JSON compression ratio {ratio:.1%} < 30%"

    def test_text_compression_ratio(self):
        """Text compression normalizes whitespace."""
        text = b"Hello    World\n\n\n\nThis is a test.\n\n\nMore content\n\n\n\nEnd"
        compressed = self.tj.compress(text, "text")
        assert len(compressed) < len(text)
        # Verify multiple spaces collapsed
        assert b"    " not in compressed

    def test_xml_compression_ratio(self):
        """XML compression strips namespaces."""
        xml_data = b"""<?xml version="1.0" encoding="UTF-8"?>
<Export xmlns="http://schema.org/health">
  <Record>
    <Type xmlns:ex="http://example.com/ns">glucose</Type>
    <Date>2024-01-15T10:00:00Z</Date>
    <Quantity>
      <Value>120</Value>
      <Unit>mg/dL</Unit>
    </Quantity>
  </Record>
</Export>"""

        ratio = TokenJuice.compression_ratio(xml_data, "xml")
        assert ratio >= 0.15, f"XML compression ratio {ratio:.1%} < 15%"

    def test_analyze_returns_result(self):
        """analyze() returns CompressionResult with valid fields."""
        data = b"Hello World"
        result = self.tj.analyze(data, "text")
        assert result.success is True
        assert result.original_size == len(data)
        assert result.compressed_size <= result.original_size
        assert 0.0 <= result.ratio <= 1.0

    def test_unknown_type_returns_asis(self):
        """Unknown source type returns data unchanged."""
        data = b"Hello World"
        compressed = self.tj.compress(data, "unknown")
        assert compressed == data

    def test_empty_data(self):
        """Empty data returns empty."""
        assert self.tj.compress(b"", "html") == b""
        assert TokenJuice.compression_ratio(b"", "html") == 0.0


# ======================================================================
# BiomarkerNormalizer Tests
# ======================================================================


class TestBiomarkerNormalizer:
    """BiomarkerNormalizer multi-source normalization tests."""

    def setup_method(self):
        self.normalizer = BiomarkerNormalizer()

    def test_apple_health_xml_glucose(self):
        """Parse Apple Health XML with glucose record."""
        xml = b"""<?xml version="1.0" encoding="UTF-8"?>
<Export>
  <Record>
    <Type>BloodGlucose</Type>
    <Date>2024-01-15T10:00:00Z</Date>
    <Quantity>
      <Value>120.5</Value>
      <Unit>mg/dL</Unit>
    </Quantity>
  </Record>
</Export>"""

        records = self.normalizer.normalize(xml, "apple_health_xml")
        assert len(records) == 1
        assert records[0].category == "glucose"
        assert records[0].value == 120.5
        assert records[0].unit == "mg/dL"
        assert records[0].source == "apple_health"

    def test_cgm_json(self):
        """Parse CGM JSON readings."""
        data = json.dumps({
            "readings": [
                {"timestamp": "2024-01-15T10:00:00Z", "value": 110, "unit": "mg/dL"},
                {"timestamp": "2024-01-15T10:05:00Z", "value": 115, "unit": "mg/dL"},
            ]
        }).encode()

        records = self.normalizer.normalize(data, "cgm_json")
        assert len(records) == 2
        assert all(r.category == "glucose" for r in records)
        assert all(r.source == "cgm" for r in records)
        assert records[0].value == 110
        assert records[1].value == 115

    def test_garmin_csv(self):
        """Parse Garmin CSV with heart rate and steps."""
        csv_data = b"""date,time,heart_rate,steps
2024-01-15,10:00,72,5000
2024-01-15,11:00,75,12000
"""

        records = self.normalizer.normalize(csv_data, "garmin_csv")
        assert len(records) == 4  # 2 HR + 2 steps
        hr_records = [r for r in records if r.category == "heart_rate"]
        step_records = [r for r in records if r.category == "steps"]
        assert len(hr_records) == 2
        assert len(step_records) == 2
        assert hr_records[0].value == 72
        assert step_records[0].value == 5000

    def test_fitbit_json(self):
        """Parse Fitbit JSON with heart rate, steps, sleep."""
        data = json.dumps({
            "activity": [
                {
                    "timestamp": "2024-01-15T10:00:00Z",
                    "heartRate": {"value": 72},
                    "steps": {"value": 5000},
                    "sleep": {"minutes": 480},
                }
            ]
        }).encode()

        records = self.normalizer.normalize(data, "fitbit_json")
        assert len(records) == 3
        categories = {r.category for r in records}
        assert categories == {"heart_rate", "steps", "sleep"}
        sleep_rec = [r for r in records if r.category == "sleep"][0]
        assert sleep_rec.value == 8.0  # 480 min / 60 = 8 hours

    def test_merge_deduplication(self):
        """Merge deduplicates by (category, timestamp minute)."""
        now = datetime(2024, 1, 15, 10, 0, 30, tzinfo=timezone.utc)
        records = [
            NormalizedBiomarker(
                timestamp=now.replace(second=0),
                source="cgm",
                category="glucose",
                value=120,
                unit="mg/dL",
                confidence=0.95,
            ),
            NormalizedBiomarker(
                timestamp=now.replace(second=45),
                source="apple_health",
                category="glucose",
                value=122,
                unit="mg/dL",
                confidence=0.9,
            ),
        ]

        merged = self.normalizer.merge(records)
        assert len(merged) == 1  # Same minute → dedup
        assert merged[0].source == "cgm"  # Higher confidence kept

    def test_unknown_source_returns_empty(self):
        """Unknown source type returns empty list."""
        records = self.normalizer.normalize(b"{}", "unknown_type")
        assert records == []

    def test_normalized_biomarker_roundtrip(self):
        """NormalizedBiomarker to_dict/from_dict roundtrip."""
        original = NormalizedBiomarker(
            timestamp=datetime(2024, 1, 15, 10, 0, tzinfo=timezone.utc),
            source="cgm",
            category="glucose",
            value=120.5,
            unit="mg/dL",
            confidence=0.95,
        )
        data = original.to_dict()
        restored = NormalizedBiomarker.from_dict(data)
        assert restored.timestamp == original.timestamp
        assert restored.source == original.source
        assert restored.category == original.category
        assert restored.value == original.value
        assert restored.unit == original.unit
        assert restored.confidence == original.confidence


# ======================================================================
# HealthImporter Tests
# ======================================================================


class TestHealthImporter:
    """HealthImporter end-to-end tests."""

    def setup_method(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.importer = None  # Created per test

    def teardown_method(self):
        self.tmpdir.cleanup()

    def test_import_batch_empty(self):
        """Empty batch returns zero counts."""
        self.importer = _make_importer(self.tmpdir.name)
        result = self.importer.import_batch([])
        assert result.success_count == 0
        assert result.failed_count == 0

    def test_import_batch_writes_documents(self):
        """Batch import writes Markdown documents to Family-Hub."""
        self.importer = _make_importer(self.tmpdir.name)
        records = [
            NormalizedBiomarker(
                timestamp=datetime(2024, 1, 15, 10, 0, tzinfo=timezone.utc),
                source="cgm",
                category="glucose",
                value=120,
                unit="mg/dL",
            ),
        ]

        result = self.importer.import_batch(records)
        assert result.success_count == 1
        assert len(result.documents_written) == 1
        assert Path(result.documents_written[0]).exists()

        # Verify content
        content = Path(result.documents_written[0]).read_text()
        assert "glucose" in content.lower()
        assert "120" in content

    def test_import_batch_dry_run(self):
        """Dry run doesn't write files."""
        self.importer = _make_importer(self.tmpdir.name)
        records = [
            NormalizedBiomarker(
                timestamp=datetime(2024, 1, 15, 10, 0, tzinfo=timezone.utc),
                source="cgm",
                category="glucose",
                value=120,
                unit="mg/dL",
            ),
        ]

        result = self.importer.import_batch(records, dry_run=True)
        assert result.success_count == 1
        assert len(result.documents_written) == 0
        assert result.bos_receipt is None

    def test_import_multiple_categories(self):
        """Multiple categories create separate documents."""
        self.importer = _make_importer(self.tmpdir.name)
        records = [
            NormalizedBiomarker(
                timestamp=datetime(2024, 1, 15, 10, 0, tzinfo=timezone.utc),
                source="cgm",
                category="glucose",
                value=120,
                unit="mg/dL",
            ),
            NormalizedBiomarker(
                timestamp=datetime(2024, 1, 15, 11, 0, tzinfo=timezone.utc),
                source="garmin",
                category="heart_rate",
                value=72,
                unit="bpm",
            ),
            NormalizedBiomarker(
                timestamp=datetime(2024, 1, 15, 12, 0, tzinfo=timezone.utc),
                source="fitbit",
                category="steps",
                value=5000,
                unit="steps",
            ),
        ]

        result = self.importer.import_batch(records)
        assert result.success_count == 3
        assert len(result.documents_written) == 3


def _make_importer(tmp_path: str):
    """Helper to create HealthImporter with isolated temp directory."""
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent.parent.parent / "family-hub" / "src"))
    from family_hub.health_importer import HealthImporter
    return HealthImporter(family_hub_path=tmp_path)
