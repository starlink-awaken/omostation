import importlib.util
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "bin/panorama/panorama-collect.py"


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


def test_missing_cell_state_is_a_legal_empty_projection(tmp_path, monkeypatch) -> None:
    module = _module()
    monkeypatch.setattr(module, "ROOT", tmp_path)
    result = module.collect_agent_cell_pool()
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
