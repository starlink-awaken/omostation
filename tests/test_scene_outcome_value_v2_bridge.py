"""Scene outcome → value-evidence/v2 bridge eligibility (human gate only)."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bin" / "ssot"))


def _load_module():
    path = ROOT / "bin" / "ssot" / "scene-outcome-recorder.py"
    spec = importlib.util.spec_from_file_location("scene_outcome_recorder_under_test", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_value_v2_skipped_for_journey_auto(tmp_path, monkeypatch):
    m = _load_module()
    evidence = tmp_path / "value-evidence.jsonl"
    monkeypatch.setattr(m, "VALUE_EVIDENCE_LOG", evidence)
    entry = {
        "ts": "2026-09-23T15:00:00Z",
        "scene_id": "personal-followup-dogfood",
        "run_id": "run-auto-skip",
        "adjudication": "accepted",
        "actor": "journey-auto-complete",
        "digest": "sha256:" + "1" * 64,
    }
    m._write_value_evidence(entry, review_seconds=10, saved_seconds=200)
    lines = [json.loads(x) for x in evidence.read_text().splitlines() if x.strip()]
    assert lines, "v1 bridge still writes"
    assert all(r.get("schema") == "value-evidence/v1" for r in lines)


def test_value_v2_skipped_when_net_below_threshold(tmp_path, monkeypatch):
    m = _load_module()
    evidence = tmp_path / "value-evidence.jsonl"
    monkeypatch.setattr(m, "VALUE_EVIDENCE_LOG", evidence)
    entry = {
        "ts": "2026-09-23T15:00:00Z",
        "scene_id": "personal-followup-dogfood",
        "run_id": "run-low-net",
        "adjudication": "accepted",
        "actor": "human",
        "digest": "sha256:" + "2" * 64,
    }
    m._write_value_evidence(entry, review_seconds=100, saved_seconds=120)
    lines = [json.loads(x) for x in evidence.read_text().splitlines() if x.strip()]
    assert lines
    assert all(r.get("schema") == "value-evidence/v1" for r in lines)


def test_legacy_scene_bridge_cannot_append_value_v2_when_baseline_present(tmp_path, monkeypatch):
    m = _load_module()
    evidence = tmp_path / "value-evidence.jsonl"
    baseline_dir = tmp_path / "baselines"
    baseline_dir.mkdir()
    baseline_id = "value-recorder-baseline-20260923-pre-v2-window"
    # Minimal frozen baseline that value-recorder.load_baseline accepts.
    baseline = {
        "schema": "value-baseline/v1",
        "baseline_id": baseline_id,
        "frozen_at": "2026-09-23T00:00:00+00:00",
        "metrics": {"scope": "unit-test"},
    }
    import hashlib

    body = {k: v for k, v in baseline.items() if k != "digest"}
    payload = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    baseline["digest"] = "sha256:" + hashlib.sha256(payload).hexdigest()
    (baseline_dir / f"{baseline_id}.json").write_text(json.dumps(baseline), encoding="utf-8")

    monkeypatch.setattr(m, "VALUE_EVIDENCE_LOG", evidence)

    # Point value-recorder BASELINE_DIR at tmp by patching after load inside bridge —
    # bridge loads module itself; monkeypatch load via env not available.
    # Instead: write baseline under the worktree path value-recorder will use.
    real_baseline_dir = ROOT / ".omo" / "state" / "value-baselines"
    real_baseline_dir.mkdir(parents=True, exist_ok=True)
    real_path = real_baseline_dir / f"{baseline_id}.json"
    created = not real_path.exists()
    if created:
        real_path.write_text(json.dumps(baseline), encoding="utf-8")
    try:
        entry = {
            "ts": "2026-09-23T15:00:00Z",
            "scene_id": "personal-followup-dogfood",
            "run_id": "run-v2-ok",
            "adjudication": "accepted",
            "actor": "human",
            "digest": "sha256:" + "3" * 64,
        }
        m._write_value_evidence(entry, review_seconds=30, saved_seconds=120)
        lines = [json.loads(x) for x in evidence.read_text().splitlines() if x.strip()]
        schemas = [r.get("schema") for r in lines]
        assert "value-evidence/v1" in schemas
        assert schemas == ["value-evidence/v1"]
    finally:
        if created and real_path.exists():
            real_path.unlink()


def test_value_recorder_rejects_direct_jsonl_append(tmp_path):
    path = ROOT / "bin" / "ssot" / "value-recorder.py"
    spec = importlib.util.spec_from_file_location("value_recorder_under_test", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    with pytest.raises(ValueError, match="direct_recording_retired_use_omo_event_ledger"):
        module.append_episode(
            {"schema": "value-evidence/v2"},
            evidence_path=tmp_path / "value-evidence.jsonl",
        )

    assert not (tmp_path / "value-evidence.jsonl").exists()
