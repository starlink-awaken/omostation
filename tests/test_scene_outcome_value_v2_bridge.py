"""Scene outcome → value-evidence/v2 bridge eligibility (human gate only)."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

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


def test_value_v2_written_for_human_when_baseline_present(tmp_path, monkeypatch):
    m = _load_module()
    evidence = tmp_path / "value-evidence.jsonl"
    baseline_dir = tmp_path / "baselines"
    baseline_dir.mkdir()
    # Minimal frozen baseline that value-recorder.load_baseline accepts.
    baseline = {
        "schema": "value-baseline/v1",
        "baseline_id": m.VALUE_V2_BASELINE_ID,
        "frozen_at": "2026-09-23T00:00:00+00:00",
        "metrics": {"scope": "unit-test"},
    }
    import hashlib

    body = {k: v for k, v in baseline.items() if k != "digest"}
    payload = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    baseline["digest"] = "sha256:" + hashlib.sha256(payload).hexdigest()
    (baseline_dir / f"{m.VALUE_V2_BASELINE_ID}.json").write_text(json.dumps(baseline), encoding="utf-8")

    monkeypatch.setattr(m, "VALUE_EVIDENCE_LOG", evidence)

    # Point value-recorder BASELINE_DIR at tmp by patching after load inside bridge —
    # bridge loads module itself; monkeypatch load via env not available.
    # Instead: write baseline under the worktree path value-recorder will use.
    real_baseline_dir = ROOT / ".omo" / "state" / "value-baselines"
    real_baseline_dir.mkdir(parents=True, exist_ok=True)
    real_path = real_baseline_dir / f"{m.VALUE_V2_BASELINE_ID}.json"
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
        assert "value-evidence/v2" in schemas
        v2 = next(r for r in lines if r.get("schema") == "value-evidence/v2")
        assert v2["qualifying"] is True
        assert v2["net_saved_seconds"] == 90
        assert v2["source_class"] == "real_human"
        assert v2["authority_receipt_digest"] == m.VALUE_V2_AUTHORITY_RECEIPT
    finally:
        if created and real_path.exists():
            real_path.unlink()
