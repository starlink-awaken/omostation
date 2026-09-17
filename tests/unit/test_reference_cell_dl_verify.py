import hashlib
import importlib.util
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "bin/gac/reference-cell-dl-verify.py"


def _module():
    spec = importlib.util.spec_from_file_location("reference_cell_dl_verify_test", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _summary(observed_at: str, *, result: str = "PASS") -> dict:
    return {
        "schema": "direct-local-reference-cell-r0-canary/v1",
        "result": result,
        "ledger_bound": False,
        "value_indicator_policy": False,
        "external_side_effects": "disabled",
        "workspace_writes": 0,
        "execution": {
            "backend": "local", "risk": "R0", "completed": True,
            "action": "read_file", "source": "ARCHITECTURE.md",
            "result_digest": "sha256:" + "a" * 64,
        },
        "verification": {"verdict": "accept", "score": 0.93, "schema": "verdict/v1"},
        "mesh": {
            "final_state": "verified", "replay_status": "replayed",
            "replay_event_count_delta": 0,
        },
        "observed_at": observed_at,
    }


def test_latest_fresh_valid_evidence_passes(tmp_path) -> None:
    module = _module()
    path = tmp_path / "attempt/evidence/rc/summary.json"
    path.parent.mkdir(parents=True)
    observed = datetime.now(UTC) - timedelta(hours=1)
    path.write_text(json.dumps(_summary(observed.isoformat())), encoding="utf-8")

    report = module.verify_latest(tmp_path, now=datetime.now(UTC))

    assert report["ok"] is True
    assert report["verdict"] == "PASS"
    assert report["evidence_digest"] == "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def test_latest_valid_stale_evidence_is_stale(tmp_path) -> None:
    module = _module()
    path = tmp_path / "attempt/evidence/rc/summary.json"
    path.parent.mkdir(parents=True)
    observed = datetime.now(UTC) - timedelta(days=8)
    path.write_text(json.dumps(_summary(observed.isoformat())), encoding="utf-8")

    report = module.verify_latest(tmp_path, now=datetime.now(UTC))

    assert report["ok"] is False
    assert report["verdict"] == "STALE"
    assert report["reason"] == "evidence_stale"
