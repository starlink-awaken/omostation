"""Tests for bin/gac/governance-health-monitor.py."""

from __future__ import annotations

import importlib.util
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "bin" / "gac" / "governance-health-monitor.py"


def _load_module():
    """Load governance-health-monitor module directly."""
    spec = importlib.util.spec_from_file_location("governance_health_monitor", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_collect_metrics_returns_required_keys() -> None:
    module = _load_module()
    metrics = module.collect_metrics()

    assert "timestamp" in metrics
    assert "convergence_errors" in metrics
    assert "convergence_warnings" in metrics
    assert "semantic_ok" in metrics
    assert "semantic_blocking" in metrics
    assert "legacy_cr_ids_count" in metrics


def test_collect_metrics_types() -> None:
    module = _load_module()
    metrics = module.collect_metrics()

    assert isinstance(metrics["timestamp"], str)
    assert isinstance(metrics["convergence_errors"], int)
    assert isinstance(metrics["convergence_warnings"], int)
    assert isinstance(metrics["semantic_ok"], bool)
    assert isinstance(metrics["semantic_blocking"], int)
    assert isinstance(metrics["legacy_cr_ids_count"], int)


def test_collect_metrics_timestamp_is_iso8601() -> None:
    module = _load_module()
    metrics = module.collect_metrics()

    # Should parse without error
    dt = datetime.fromisoformat(metrics["timestamp"])
    assert dt.tzinfo is not None


def test_collect_metrics_legacy_cr_ids_count_positive() -> None:
    module = _load_module()
    metrics = module.collect_metrics()

    # LEGACY_CR_IDS has ~60 entries in the real codebase
    assert metrics["legacy_cr_ids_count"] > 0


def test_append_history_creates_file(tmp_path: Path) -> None:
    module = _load_module()
    history_file = tmp_path / "history.json"

    metrics = {
        "timestamp": datetime.now(UTC).isoformat(),
        "convergence_errors": 0,
        "convergence_warnings": 0,
        "semantic_ok": True,
        "semantic_blocking": 0,
        "legacy_cr_ids_count": 60,
    }

    count = module.append_history(history_file, metrics)

    assert count == 1
    assert history_file.exists()
    data = json.loads(history_file.read_text(encoding="utf-8"))
    assert len(data) == 1
    assert data[0]["convergence_errors"] == 0


def test_append_history_appends_to_existing(tmp_path: Path) -> None:
    module = _load_module()
    history_file = tmp_path / "history.json"

    metrics1 = {
        "timestamp": "2026-08-20T00:00:00+00:00",
        "convergence_errors": 1,
        "convergence_warnings": 2,
        "semantic_ok": False,
        "semantic_blocking": 1,
        "legacy_cr_ids_count": 60,
    }
    metrics2 = {
        "timestamp": "2026-08-21T00:00:00+00:00",
        "convergence_errors": 0,
        "convergence_warnings": 0,
        "semantic_ok": True,
        "semantic_blocking": 0,
        "legacy_cr_ids_count": 61,
    }

    module.append_history(history_file, metrics1)
    count = module.append_history(history_file, metrics2)

    assert count == 2
    data = json.loads(history_file.read_text(encoding="utf-8"))
    assert len(data) == 2
    assert data[0]["convergence_errors"] == 1
    assert data[1]["convergence_errors"] == 0


def test_append_history_prunes_beyond_max(tmp_path: Path) -> None:
    module = _load_module()
    history_file = tmp_path / "history.json"

    # Write 95 entries (exceeds MAX_HISTORY_DAYS=90)
    for i in range(95):
        metrics = {
            "timestamp": f"2026-08-{(i % 28) + 1:02d}T00:00:00+00:00",
            "convergence_errors": i,
            "convergence_warnings": 0,
            "semantic_ok": True,
            "semantic_blocking": 0,
            "legacy_cr_ids_count": 60,
        }
        module.append_history(history_file, metrics)

    data = json.loads(history_file.read_text(encoding="utf-8"))
    assert len(data) == 90
    # Last entry should be the 95th (index 94)
    assert data[-1]["convergence_errors"] == 94


def test_append_history_handles_corrupt_file(tmp_path: Path) -> None:
    module = _load_module()
    history_file = tmp_path / "history.json"
    history_file.write_text("not valid json", encoding="utf-8")

    metrics = {
        "timestamp": datetime.now(UTC).isoformat(),
        "convergence_errors": 0,
        "convergence_warnings": 0,
        "semantic_ok": True,
        "semantic_blocking": 0,
        "legacy_cr_ids_count": 60,
    }

    count = module.append_history(history_file, metrics)
    assert count == 1
    data = json.loads(history_file.read_text(encoding="utf-8"))
    assert len(data) == 1


def test_append_history_creates_parent_dirs(tmp_path: Path) -> None:
    module = _load_module()
    history_file = tmp_path / "deep" / "nested" / "history.json"

    metrics = {
        "timestamp": datetime.now(UTC).isoformat(),
        "convergence_errors": 0,
        "convergence_warnings": 0,
        "semantic_ok": True,
        "semantic_blocking": 0,
        "legacy_cr_ids_count": 60,
    }

    count = module.append_history(history_file, metrics)
    assert count == 1
    assert history_file.exists()


def test_count_legacy_cr_ids() -> None:
    module = _load_module()
    count = module._count_legacy_cr_ids()

    # LEGACY_CR_IDS has ~60 entries
    assert count > 0
    assert isinstance(count, int)
