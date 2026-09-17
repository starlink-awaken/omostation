import hashlib
import importlib.util
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "bin/ssot/agent-cell-pool-live-smoke.py"


def _module():
    spec = importlib.util.spec_from_file_location("agent_cell_pool_live_smoke", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _receipt_digest(receipt: dict) -> str:
    payload = {key: value for key, value in receipt.items() if key != "receipt_digest"}
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def test_live_smoke_persists_real_cell_lifecycle_and_hash_chained_receipt(tmp_path) -> None:
    module = _module()
    state_file = tmp_path / "agent-cell" / "cell_states.json"
    report = module.run_smoke(state_file)

    assert report["ok"] is True
    assert report["external_side_effects"] == "none"
    assert report["value_claim"] == "NOT_PROVEN"
    assert report["pool_status"]["total_cells"] == 1
    assert report["pool_status"]["active_episodes"] == 0

    states = json.loads(state_file.read_text(encoding="utf-8"))
    state = states[report["cell_id"]]
    assert state["state"] == "idle"
    assert state["episode_id"] is None
    assert state["context"]["verdict"] == "accept"
    assert len(state["handoff_log"]) == 2
    assert state["handoff_log"][0]["schema"] == "handoff/v1"
    assert state["handoff_log"][1]["schema"] == "handoff/v1"

    receipt_file = tmp_path / "agent-cell" / "live-smoke-receipts.jsonl"
    rows = [json.loads(line) for line in receipt_file.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 1
    assert rows[0]["schema"] == "agent-cell-pool-live-smoke/v1"
    assert rows[0]["previous_receipt_digest"] is None
    assert rows[0]["receipt_digest"] == report["receipt_digest"]
    assert _receipt_digest(rows[0]) == rows[0]["receipt_digest"]
    assert rows[0]["persisted_state_sha256"] == module._sha256(state)


def test_second_smoke_chains_to_previous_durable_receipt(tmp_path) -> None:
    module = _module()
    state_file = tmp_path / "cell_states.json"
    first = module.run_smoke(state_file)
    second = module.run_smoke(state_file)

    receipt_file = tmp_path / "live-smoke-receipts.jsonl"
    rows = [json.loads(line) for line in receipt_file.read_text(encoding="utf-8").splitlines()]
    assert first["cell_id"] != second["cell_id"]
    assert len(rows) == 2
    assert rows[0]["previous_receipt_digest"] is None
    assert rows[1]["previous_receipt_digest"] == rows[0]["receipt_digest"]
    assert _receipt_digest(rows[1]) == rows[1]["receipt_digest"]


def test_receipt_loader_rejects_non_object_lines(tmp_path) -> None:
    module = _module()
    path = tmp_path / "receipts.jsonl"
    path.write_text("[]\n", encoding="utf-8")
    try:
        module._load_receipts(path)
    except ValueError as exc:
        assert str(exc) == "receipt line is not an object"
    else:
        raise AssertionError("expected malformed receipt line to fail closed")


def test_verify_mode_recomputes_durable_receipt_and_state_binding(tmp_path) -> None:
    module = _module()
    state_file = tmp_path / "cell_states.json"
    module.run_smoke(state_file)
    report = module.verify_smoke(state_file)
    assert report["schema"] == "agent-cell-pool-live-smoke-verification/v1"
    assert report["ok"] is True
    assert report["verdict"] == "PASS"
    assert report["state_count"] == 1
    assert report["receipt_count"] == 1
    assert report["digests_ok"] is True
    assert report["chain_ok"] is True
    assert report["state_bindings_ok"] is True
    assert report["lifecycle_ok"] is True


def test_verify_mode_fails_closed_on_tampered_state_binding(tmp_path) -> None:
    module = _module()
    state_file = tmp_path / "cell_states.json"
    module.run_smoke(state_file)
    states = json.loads(state_file.read_text(encoding="utf-8"))
    next(iter(states.values()))["context"]["verdict"] = "reject"
    state_file.write_text(json.dumps(states), encoding="utf-8")
    report = module.verify_smoke(state_file)
    assert report["ok"] is False
    assert report["verdict"] == "FAILED"
    assert report["state_bindings_ok"] is False
    assert report["digests_ok"] is True


def test_cleanup_expired_states_removes_only_expired_smoke_states(tmp_path) -> None:
    module = _module()
    path = tmp_path / "cell_states.json"
    now = datetime.now(UTC)
    states = {
        "cell-old": {"cell_id": "cell-old", "saved_at": (now - timedelta(hours=25)).isoformat()},
        "cell-new": {"cell_id": "cell-new", "saved_at": now.isoformat()},
        "cell-invalid": {"cell_id": "cell-invalid", "saved_at": "not-a-time"},
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(states), encoding="utf-8")

    report = module._cleanup_expired_states(path, now=now)

    retained = json.loads(path.read_text(encoding="utf-8"))
    assert report["removed_count"] == 1
    assert report["removed_cell_ids"] == ["cell-old"]
    assert report["retained_count"] == 2
    assert set(retained) == {"cell-new", "cell-invalid"}


def test_verify_skips_expired_state_binding_but_keeps_full_receipt_chain(tmp_path) -> None:
    module = _module()
    state_file = tmp_path / "cell_states.json"
    module.run_smoke(state_file)
    receipt_file = tmp_path / "live-smoke-receipts.jsonl"
    rows = [json.loads(line) for line in receipt_file.read_text(encoding="utf-8").splitlines()]
    rows[0]["finished_at"] = (datetime.now(UTC) - timedelta(hours=25)).isoformat()
    rows[0]["receipt_digest"] = module._receipt_digest(rows[0])
    receipt_file.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    state_file.unlink()

    report = module.verify_smoke(state_file)

    assert report["ok"] is True
    assert report["verdict"] == "PASS"
    assert report["state_count"] == 0
    assert report["receipt_count"] == 1
    assert report["state_bindings_checked"] == 0
    assert report["state_bindings_skipped_expired"] == 1
    assert report["chain_ok"] is True
