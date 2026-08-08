"""BET-Y1Q2-T6-01: Rule vitality tracking + dynamic downgrade tests.

Covers:
  - rule-vitality-tracker.py: record, read, query, compute_all_summaries
  - rule-vitality-report.py: zero-violations, suggest-downgrade guardrails
  - gac-rule-gate-mapping.py: mapping generation
"""

from __future__ import annotations

import importlib.util
import json
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def tracker():
    return _load_module("rule_vitality_tracker", ROOT / "bin" / "gac" / "rule-vitality-tracker.py")


@pytest.fixture
def tmp_vitality(tmp_path):
    return tmp_path / "rule-vitality.jsonl"


class TestRuleVitalityTracker:
    def test_record_and_read(self, tracker, tmp_vitality):
        tracker.record_vitality("CR-TEST-1", "check-foo", violated=False, enforcement="required", path=tmp_vitality)
        tracker.record_vitality("CR-TEST-1", "check-foo", violated=True, enforcement="required", path=tmp_vitality)
        entries = tracker.read_vitality(tmp_vitality)
        assert len(entries) == 2
        assert entries[0]["rule_id"] == "CR-TEST-1"
        assert entries[0]["violated"] is False
        assert entries[1]["violated"] is True

    def test_query_vitality(self, tracker, tmp_vitality):
        for i in range(5):
            tracker.record_vitality("CR-TEST-2", "check-bar", violated=(i == 3), enforcement="advisory", path=tmp_vitality)
        summary = tracker.query_vitality("CR-TEST-2", window_days=30, path=tmp_vitality)
        assert summary["total_evaluations"] == 5
        assert summary["total_violations"] == 1
        assert abs(summary["violation_rate"] - 0.2) < 1e-6
        assert summary["last_violation"] is not None

    def test_query_no_data(self, tracker, tmp_vitality):
        summary = tracker.query_vitality("CR-NONEXISTENT", window_days=30, path=tmp_vitality)
        assert summary["total_evaluations"] == 0
        assert summary["total_violations"] == 0

    def test_compute_all_summaries(self, tracker, tmp_vitality):
        tracker.record_vitality("CR-A", "g1", path=tmp_vitality)
        tracker.record_vitality("CR-B", "g2", violated=True, path=tmp_vitality)
        tracker.record_vitality("CR-A", "g1", path=tmp_vitality)
        summaries = tracker.compute_all_summaries(window_days=30, path=tmp_vitality)
        rule_ids = {s["rule_id"] for s in summaries}
        assert rule_ids == {"CR-A", "CR-B"}
        a_summary = next(s for s in summaries if s["rule_id"] == "CR-A")
        assert a_summary["total_evaluations"] == 2
        assert a_summary["total_violations"] == 0

    def test_record_with_details(self, tracker, tmp_vitality):
        tracker.record_vitality("CR-DET", "g1", details="some context", path=tmp_vitality)
        entries = tracker.read_vitality(tmp_vitality)
        assert entries[0]["details"] == "some context"

    def test_empty_read(self, tracker, tmp_path):
        empty = tmp_path / "nonexistent.jsonl"
        assert tracker.read_vitality(empty) == []


class TestRuleVitalityReport:
    @pytest.fixture(scope="class")
    def report_mod(self):
        import sys
        bin_gac = str(ROOT / "bin" / "gac")
        if bin_gac not in sys.path:
            sys.path.insert(0, bin_gac)
        return _load_module("rule_vitality_report", ROOT / "bin" / "gac" / "rule-vitality-report.py")

    def test_zero_violations_with_data(self, tracker, report_mod, tmp_path, monkeypatch):
        vitality_path = tmp_path / "vitality.jsonl"
        for i in range(3):
            tracker.record_vitality("CR-X", "g1", violated=False, enforcement="advisory", path=vitality_path)
        tracker.record_vitality("CR-Y", "g2", violated=True, enforcement="required", path=vitality_path)

        monkeypatch.setattr(report_mod, "read_vitality", lambda: tracker.read_vitality(vitality_path))
        results = report_mod._zero_violations_report(window_days=30)
        rule_ids = {r["rule_id"] for r in results}
        assert "CR-X" in rule_ids
        assert "CR-Y" not in rule_ids

    def test_suggest_downgrade_min_evaluations_guard(self, report_mod, monkeypatch):
        monkeypatch.setattr(report_mod, "read_vitality", lambda: [])
        suggestions = report_mod._suggest_downgrade(window_days=60)
        assert suggestions == []

    def test_is_protected(self, report_mod):
        assert report_mod._is_protected({"executor": ["hook_pre_edit"]}) is True
        assert report_mod._is_protected({"executor": ["ci_gate"]}) is False
        assert report_mod._is_protected({"executor": []}) is False


class TestGateMapping:
    def test_mapping_file_exists(self):
        mapping_path = ROOT / ".omo" / "_truth" / "registry" / "rule-gate-mapping.yaml"
        assert mapping_path.exists()

    def test_mapping_has_required_keys(self):
        import yaml
        mapping_path = ROOT / ".omo" / "_truth" / "registry" / "rule-gate-mapping.yaml"
        data = yaml.safe_load(mapping_path.read_text(encoding="utf-8"))
        assert "gate_to_rules" in data
        assert "rule_to_gates" in data
        assert "stats" in data

    def test_mapping_stats_consistent(self):
        import yaml
        mapping_path = ROOT / ".omo" / "_truth" / "registry" / "rule-gate-mapping.yaml"
        data = yaml.safe_load(mapping_path.read_text(encoding="utf-8"))
        stats = data["stats"]
        assert stats["mapped_rules"] == len(data["rule_to_gates"])
        assert stats["total_rules"] > 0
        assert stats["total_gates"] > 0
        assert stats["mapped_rules"] + stats["unmapped_rules"] == stats["total_rules"]
