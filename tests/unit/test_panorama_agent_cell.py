import importlib.util
import json
import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "bin/panorama/panorama-collect.py"
SMOKE_SCRIPT = ROOT / "bin/ssot/agent-cell-pool-live-smoke.py"


def _module():
    spec = importlib.util.spec_from_file_location("panorama_agent_cell", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_states(module, states: object) -> Path:
    state_dir = module.ROOT / ".omo/state/agent-cell"
    state_dir.mkdir(parents=True, exist_ok=True)
    path = state_dir / "cell_states.json"
    path.write_text(json.dumps(states), encoding="utf-8")
    return path


def _smoke_module():
    spec = importlib.util.spec_from_file_location("panorama_test_live_smoke", SMOKE_SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _install_verifier(root: Path) -> None:
    target = root / "bin/ssot"
    target.mkdir(parents=True, exist_ok=True)
    shutil.copy(SMOKE_SCRIPT, target / SMOKE_SCRIPT.name)


def test_missing_cell_state_is_a_legal_empty_projection(tmp_path, monkeypatch) -> None:
    module = _module()
    monkeypatch.setattr(module, "ROOT", tmp_path)
    _install_verifier(tmp_path)
    result = module.collect_agent_cell_pool()
    receipts = result.pop("receipt_verification")
    assert result["schema"] == "agent-cell-pool-projection/v1"
    assert result["available"] is False
    assert result["live"] is False
    assert result["verdict"] == "EMPTY"
    assert result == {
        "schema": "agent-cell-pool-projection/v1",
        "source": "runtime://.omo/state/agent-cell/cell_states.json",
        "available": False,
        "live": False,
        "verdict": "EMPTY",
        "total": 0,
        "active": 0,
        "failed": 0,
        "state_distribution": {},
        "latest_saved_at": None,
        "age_seconds": None,
        "cells": [],
    }
    assert receipts["verdict"] == "EMPTY"
    assert receipts["receipt_count"] == 0
    assert receipts["ok"] is True


def test_fresh_active_state_is_summarized_without_context_leak(tmp_path, monkeypatch) -> None:
    module = _module()
    monkeypatch.setattr(module, "ROOT", tmp_path)
    saved = datetime.now(UTC).isoformat()
    _write_states(
        module,
        {
            "cell-a": {
                "cell_id": "cell-a",
                "state": "executing",
                "episode_id": "episode-1",
                "current_role": "executor",
                "handoff_log": [{"schema": "handoff/v1"}],
                "saved_at": saved,
                "context": {"intent": "SECRET_INTENT", "result": "SECRET_RESULT"},
            }
        },
    )
    result = module.collect_agent_cell_pool()
    result.pop("receipt_verification")
    assert result["available"] is True
    assert result["live"] is True
    assert result["verdict"] == "PASS"
    assert result["total"] == 1
    assert result["active"] == 1
    assert result["failed"] == 0
    assert result["state_distribution"] == {"executing": 1}
    assert result["cells"] == [{
        "cell_id": "cell-a",
        "state": "executing",
        "episode_id": "episode-1",
        "current_role": "executor",
        "handoff_count": 1,
        "saved_at": saved,
    }]
    assert "SECRET_INTENT" not in json.dumps(result)
    assert "SECRET_RESULT" not in json.dumps(result)


def test_failed_state_fails_visible_and_stale_state_is_not_live(tmp_path, monkeypatch) -> None:
    module = _module()
    monkeypatch.setattr(module, "ROOT", tmp_path)
    fresh = (datetime.now(UTC) - timedelta(seconds=10)).isoformat()
    stale = (datetime.now(UTC) - timedelta(seconds=301)).isoformat()
    _write_states(
        module,
        {
            "cell-failed": {"cell_id": "cell-failed", "state": "failed", "saved_at": fresh},
            "cell-stale": {"cell_id": "cell-stale", "state": "idle", "saved_at": stale},
        },
    )
    result = module.collect_agent_cell_pool()
    assert result["available"] is True
    assert result["live"] is True
    assert result["verdict"] == "FAILED"
    assert result["failed"] == 1

    _write_states(module, {"cell-stale": {"cell_id": "cell-stale", "state": "idle", "saved_at": stale}})
    result = module.collect_agent_cell_pool()
    assert result["available"] is True
    assert result["live"] is False
    assert result["verdict"] == "STALE"
    assert result["age_seconds"] >= 301


def test_malformed_state_is_visible_and_fail_closed(tmp_path, monkeypatch) -> None:
    module = _module()
    monkeypatch.setattr(module, "ROOT", tmp_path)
    path = module.ROOT / ".omo/state/agent-cell/cell_states.json"
    path.parent.mkdir(parents=True)
    path.write_text("[]", encoding="utf-8")
    result = module.collect_agent_cell_pool()
    assert result["available"] is False
    assert result["verdict"] == "UNPARSEABLE"
    assert result["error"] == "ValueError"


def test_collector_projects_valid_receipt_chain(tmp_path, monkeypatch) -> None:
    panorama = _module()
    smoke = _smoke_module()
    monkeypatch.setattr(panorama, "ROOT", tmp_path)
    _install_verifier(tmp_path)
    state_file = tmp_path / ".omo/state/agent-cell/cell_states.json"
    state_file.parent.mkdir(parents=True, exist_ok=True)
    smoke.run_smoke(state_file)
    result = panorama.collect_agent_cell_pool()
    receipts = result["receipt_verification"]
    assert result["verdict"] == "PASS"
    assert result["live"] is True
    assert receipts["ok"] is True
    assert receipts["verdict"] == "PASS"
    assert receipts["receipt_count"] == 1
    assert receipts["state_bindings_ok"] is True
    assert receipts["latest_receipt_digest"]


def test_collector_fails_closed_on_broken_receipt_chain(tmp_path, monkeypatch) -> None:
    panorama = _module()
    smoke = _smoke_module()
    monkeypatch.setattr(panorama, "ROOT", tmp_path)
    _install_verifier(tmp_path)
    state_file = tmp_path / ".omo/state/agent-cell/cell_states.json"
    state_file.parent.mkdir(parents=True, exist_ok=True)
    smoke.run_smoke(state_file)
    receipt_file = state_file.parent / "live-smoke-receipts.jsonl"
    rows = [json.loads(line) for line in receipt_file.read_text(encoding="utf-8").splitlines()]
    rows[0]["receipt_digest"] = "0" * 64
    receipt_file.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    result = panorama.collect_agent_cell_pool()
    assert result["verdict"] == "FAILED"
    assert result["receipt_verification"]["ok"] is False
    assert result["receipt_verification"]["verdict"] == "FAILED"
    assert result["receipt_verification"]["digests_ok"] is False


def test_collector_projects_semantic_verifier_fail_closed(tmp_path, monkeypatch) -> None:
    module = _module()
    monkeypatch.setattr(
        module,
        "_verify_agent_cell_semantic",
        lambda: {
            "schema": "agent-cell-semantic-smoke/v1",
            "ok": True,
            "verdict": "PASS",
            "receipt_count": 2,
            "chain_ok": True,
            "digests_ok": True,
            "bindings_ok": True,
            "lifecycle_ok": True,
            "latest_run_id": "semantic-smoke-test",
            "latest_receipt_digest": "sha256:" + "0" * 64,
        },
    )
    result = module.collect_agent_cell_semantic()
    assert result["schema"] == "agent-cell-semantic-projection/v1"
    assert result["available"] is True
    assert result["verdict"] == "PASS"
    assert result["receipt_count"] == 2
    assert result["receipt_chain_ok"] is True
    assert result["role_bindings_ok"] is True
    assert result["mesh_bindings_ok"] is True
    assert result["queue_bindings_ok"] is True
    assert result["claims_authority_invoked"] is False
