"""Tests for runtime state_schema and kei_probe."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from runtime.kei_probe import count_last_24h, last_age_hours, main
from runtime.state_schema import validate_runtime_health_snapshot


class TestValidateRuntimeHealthSnapshot:
    def test_valid_payload(self):
        result = validate_runtime_health_snapshot(
            {"services": {"agora": {"status": "ok"}}}
        )
        assert result["services"]["agora"]["status"] == "ok"

    def test_not_a_dict(self):
        with pytest.raises(ValueError, match="must be a mapping"):
            validate_runtime_health_snapshot("not a dict")

    def test_governance_keys_rejected(self):
        with pytest.raises(ValueError, match="governance-only"):
            validate_runtime_health_snapshot(
                {
                    "services": {"agora": {"status": "ok"}},
                    "current_phase": "34",
                }
            )

    def test_missing_services(self):
        with pytest.raises(ValueError, match="services must be a mapping"):
            validate_runtime_health_snapshot({"status": "ok"})

    def test_services_not_dict(self):
        with pytest.raises(ValueError, match="services must be a mapping"):
            validate_runtime_health_snapshot({"services": "not a dict"})


# ── kei_probe ──


class TestCountLast24h:
    def test_file_not_exists(self):
        assert count_last_24h(Path("/fake.jsonl")) == 0

    def test_recent_events(self, tmp_path: Path):
        now = datetime.now(timezone.utc)
        lines = [
            json.dumps({"ts": now.isoformat()}),
            json.dumps({"ts": (now - timedelta(hours=2)).isoformat()}),
        ]
        path = tmp_path / "kei_audit.jsonl"
        path.write_text("\n".join(lines), encoding="utf-8")
        assert count_last_24h(path) == 2

    def test_old_events(self, tmp_path: Path):
        old = (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat()
        path = tmp_path / "kei_audit.jsonl"
        path.write_text(json.dumps({"ts": old}), encoding="utf-8")
        assert count_last_24h(path) == 0

    def test_bad_json_skipped(self, tmp_path: Path):
        path = tmp_path / "kei_audit.jsonl"
        path.write_text("not json\n{", encoding="utf-8")
        assert count_last_24h(path) == 0


class TestLastAgeHours:
    def test_file_not_exists(self):
        assert last_age_hours(Path("/fake.jsonl")) == float("inf")

    def test_recent_event(self, tmp_path: Path):
        now = datetime.now(timezone.utc)
        path = tmp_path / "kei_audit.jsonl"
        path.write_text(json.dumps({"ts": now.isoformat()}), encoding="utf-8")
        age = last_age_hours(path)
        assert 0 <= age < 1

    def test_old_event(self, tmp_path: Path):
        old = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
        path = tmp_path / "kei_audit.jsonl"
        path.write_text(json.dumps({"ts": old}), encoding="utf-8")
        age = last_age_hours(path)
        assert 23 <= age <= 25

    def test_empty_file(self, tmp_path: Path):
        path = tmp_path / "kei_audit.jsonl"
        path.write_text("", encoding="utf-8")
        assert last_age_hours(path) == float("inf")


class TestMain:
    @patch("runtime.kei_probe.count_last_24h")
    @patch("runtime.kei_probe.argparse.ArgumentParser.parse_args")
    def test_count_24h(self, mock_args, mock_count):
        mock_args.return_value = MagicMock(
            count_24h=True, last_age_hours=False, path="/fake.jsonl"
        )
        mock_count.return_value = 5
        assert main() == 0

    @patch("runtime.kei_probe.count_last_24h")
    @patch("runtime.kei_probe.argparse.ArgumentParser.parse_args")
    def test_count_24h_zero(self, mock_args, mock_count):
        mock_args.return_value = MagicMock(
            count_24h=True, last_age_hours=False, path="/fake.jsonl"
        )
        mock_count.return_value = 0
        assert main() == 1

    @patch("runtime.kei_probe.last_age_hours")
    @patch("runtime.kei_probe.argparse.ArgumentParser.parse_args")
    def test_last_age_hours(self, mock_args, mock_age):
        mock_args.return_value = MagicMock(
            count_24h=False, last_age_hours=True, path="/fake.jsonl"
        )
        mock_age.return_value = 2.5
        assert main() == 0

    @patch("runtime.kei_probe.last_age_hours")
    @patch("runtime.kei_probe.argparse.ArgumentParser.parse_args")
    def test_last_age_hours_exceeded(self, mock_args, mock_age):
        mock_args.return_value = MagicMock(
            count_24h=False, last_age_hours=True, path="/fake.jsonl"
        )
        mock_age.return_value = 48.0
        assert main() == 1
