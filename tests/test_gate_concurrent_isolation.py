"""Tests for the concurrent-write isolation logic in gac-local-gate.py.

The gate runs many subprocesses against read-side state files
(.omo/state/*.yaml, .omo/_delivery/observability/events.jsonl, etc).
When concurrent agents also write to those files mid-run, gate
results become torn. The fix: snapshot (mtime, size) fingerprints at
gate start, compare after all checks complete, emit a soft finding
topic so operators know the result may have been impacted.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "bin" / "gac" / "gac-local-gate.py"
_MODULE = "_gate_concurrent_isolation_test"


def _load_script_module():
    spec = importlib.util.spec_from_file_location(_MODULE, SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[_MODULE] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def gate():
    return _load_script_module()


def _write_state_file(ws: Path, rel: str, content: str = "test: 1\n") -> None:
    p = ws / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


def test_snapshot_returns_one_entry_per_path(gate, tmp_path, monkeypatch):
    """Snapshot reads all 8 known read-side paths and returns a dict."""
    # Create the file tree so each path exists
    for rel in gate.SNAPSHOT_PATHS:
        _write_state_file(tmp_path, rel)

    monkeypatch.setattr(gate, "WORKSPACE", tmp_path)
    fp = gate._read_state_fingerprint()
    assert len(fp) == len(gate.SNAPSHOT_PATHS)
    assert all(rel in fp for rel in gate.SNAPSHOT_PATHS)
    for rel, (mtime, size) in fp.items():
        assert mtime > 0, f"{rel} should have non-zero mtime"
        assert size >= 0, f"{rel} should have valid size"


def test_snapshot_handles_missing_files(gate, tmp_path, monkeypatch):
    """Missing files get (0.0, -1) sentinel rather than raising."""
    # tmp_path is empty — no state files
    monkeypatch.setattr(gate, "WORKSPACE", tmp_path)
    fp = gate._read_state_fingerprint()
    assert all(v == (0.0, -1) for v in fp.values())


def test_check_drift_detects_changed_file(gate, tmp_path, monkeypatch):
    """Modifying a file between snapshots produces drift entry."""
    monkeypatch.setattr(gate, "WORKSPACE", tmp_path)
    _write_state_file(tmp_path, gate.SNAPSHOT_PATHS[0], "v1: 1\n")
    snap = gate._read_state_fingerprint()

    # Modify the file
    (tmp_path / gate.SNAPSHOT_PATHS[0]).write_text("v2: plenty more content here\n", encoding="utf-8")

    drift = gate._check_drift(snap)
    assert gate.SNAPSHOT_PATHS[0] in drift


def test_check_drift_returns_empty_when_unchanged(gate, tmp_path, monkeypatch):
    """No drift when nothing changed."""
    monkeypatch.setattr(gate, "WORKSPACE", tmp_path)
    for rel in gate.SNAPSHOT_PATHS:
        _write_state_file(tmp_path, rel)
    snap = gate._read_state_fingerprint()
    drift = gate._check_drift(snap)
    assert drift == []


def test_update_drift_topic_appends_soft_warning(gate, tmp_path):
    """Drift finding is added as a soft topic, not a hard failure."""
    report: dict = {"finding_topics": []}
    drift = [gate.SNAPSHOT_PATHS[0]]
    gate._update_drift_topic(report, drift)

    assert len(report["finding_topics"]) == 1
    topic = report["finding_topics"][0]
    assert topic["topic"] == "concurrent-write-drift"
    assert topic["severity"] == "warn"
    assert topic["blocking"] is False
    assert gate.SNAPSHOT_PATHS[0] in topic["summary"]


def test_update_drift_topic_noop_when_no_drift(gate):
    """Empty drift list does not append a topic."""
    report: dict = {"finding_topics": []}
    gate._update_drift_topic(report, [])
    assert report["finding_topics"] == []


def test_drift_detection_end_to_end(gate, tmp_path, monkeypatch):
    """Full cycle: snapshot at gate start, modify mid-run, detect drift."""
    monkeypatch.setattr(gate, "WORKSPACE", tmp_path)
    _write_state_file(tmp_path, gate.SNAPSHOT_PATHS[0], "before: 1\n")
    _write_state_file(tmp_path, gate.SNAPSHOT_PATHS[1], "static: 1\n")
    snap = gate._read_state_fingerprint()

    # Simulate concurrent write to first file
    (tmp_path / gate.SNAPSHOT_PATHS[0]).write_text(
        "after: more content here, different size and mtime\n",
        encoding="utf-8",
    )

    drift = gate._check_drift(snap)
    assert gate.SNAPSHOT_PATHS[0] in drift
    assert gate.SNAPSHOT_PATHS[1] not in drift
    assert len(drift) == 1