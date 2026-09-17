import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "bin/ssot/agent-cell-semantic-smoke.py"


def _module():
    spec = importlib.util.spec_from_file_location("agent_cell_semantic_smoke", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_semantic_smoke_persists_and_reloads_role_capsule_mesh_queue(tmp_path, monkeypatch) -> None:
    module = _module()
    monkeypatch.setattr(module, "STATE_DIR", tmp_path)
    report = module.run_smoke()

    assert report["ok"] is True
    assert report["claims_authority_invoked"] is False
    assert report["external_side_effects"] == "none"
    assert report["value_claim"] == "NOT_PROVEN"
    assert (tmp_path / "roles.jsonl").is_file()
    assert (tmp_path / "capsules.jsonl").is_file()
    assert list((tmp_path / ".omo").rglob("events.jsonl"))
    assert (tmp_path / "task-queue.sqlite3").is_file()
    assert (tmp_path / "semantic-smoke-receipts.jsonl").is_file()


def test_second_semantic_smoke_reuses_roles_and_chains_receipts(tmp_path, monkeypatch) -> None:
    module = _module()
    monkeypatch.setattr(module, "STATE_DIR", tmp_path)
    first = module.run_smoke()
    second = module.run_smoke()
    verification = module.verify_latest()

    assert first["ok"] and second["ok"]
    assert first["capsule_id"] != second["capsule_id"]
    assert verification["verdict"] == "PASS"
    assert verification["receipt_count"] == 2
    assert verification["chain_ok"] is True
    assert verification["digests_ok"] is True


def test_verify_latest_is_empty_before_first_run(tmp_path, monkeypatch) -> None:
    module = _module()
    monkeypatch.setattr(module, "STATE_DIR", tmp_path)
    report = module.verify_latest()
    assert report == {
        "schema": "agent-cell-semantic-smoke/v1",
        "ok": True,
        "verdict": "EMPTY",
        "receipt_count": 0,
    }
