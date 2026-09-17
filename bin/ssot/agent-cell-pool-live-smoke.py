#!/usr/bin/env python3
"""Controlled AGE-v2 Agent Cell Pool live smoke.

The smoke drives the real OMO CellPool scheduler through
planner -> executor -> verifier -> completed, then persists the resulting Cell
state and an append-only hash-chained runtime receipt.  It uses a fixed
deterministic intent, performs no provider/tool/filesystem effect, and makes no
BET value or completion claim.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_STATE_FILE = ROOT / ".omo/state/agent-cell/cell_states.json"
SCHEMA = "agent-cell-pool-live-smoke/v1"


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _load_receipts(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError("receipt line is not an object")
            rows.append(row)
    return rows


def _receipt_digest(receipt: dict[str, Any]) -> str:
    return _sha256({key: value for key, value in receipt.items() if key != "receipt_digest"})


def _append_receipt(path: Path, receipt: dict[str, Any]) -> dict[str, Any]:
    rows = _load_receipts(path)
    previous = rows[-1].get("receipt_digest") if rows and isinstance(rows[-1].get("receipt_digest"), str) else None
    candidate = {**receipt, "previous_receipt_digest": previous}
    candidate["receipt_digest"] = _receipt_digest(candidate)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(candidate, ensure_ascii=False, sort_keys=True) + "\n")
        handle.flush()
    stored = _load_receipts(path)[-1]
    if _receipt_digest(stored) != stored["receipt_digest"]:
        raise RuntimeError("durable smoke receipt digest verification failed")
    return stored


def run_smoke(state_file: Path) -> dict[str, Any]:
    """Drive one real, bounded CellPool lifecycle against ``state_file``."""
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    omo_src = ROOT / "projects/omo/src"
    if omo_src.is_dir() and str(omo_src) not in sys.path:
        sys.path.insert(0, str(omo_src))
    try:
        from omo.resident import cell_state
        from omo.resident.cell_pool import CellPool
    except ImportError as exc:
        raise RuntimeError("OMO source is unavailable; initialize projects/omo") from exc

    state_file = state_file.resolve()
    state_file.parent.mkdir(parents=True, exist_ok=True)
    # CellStateManager reads module constants; bind them to the explicit smoke
    # target so tests and operators can isolate the runtime without modifying OMO.
    cell_state.STATE_DIR = state_file.parent
    cell_state.STATE_FILE = state_file

    now = datetime.now(UTC)
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    token = uuid.uuid4().hex[:8]
    episode_id = f"episode-agent-cell-live-smoke-{stamp}-{token}"
    cell_id = f"cell-live-smoke-{stamp}-{token}"
    started_at = now.isoformat()

    intent = {
        "schema": "agent-cell-smoke-intent/v1",
        "scenario": "pool_lifecycle",
        "external_side_effects": "none",
    }
    plan = {"schema": "agent-cell-smoke-plan/v1", "steps": ["verify_scheduler"]}
    result = {"schema": "agent-cell-smoke-result/v1", "status": "ok"}

    pool = CellPool(max_cells=2, min_cells=1, auto_scale=False, enable_persistence=True)
    dispatch = pool.dispatch_episode(episode_id, intent)
    if dispatch.get("state") != "planning" or dispatch.get("current_role") != "planner":
        raise RuntimeError(f"unexpected dispatch state: {dispatch}")
    assigned_cell_id = pool.episode_assignments.get(episode_id)
    if assigned_cell_id is None:
        raise RuntimeError("CellPool did not persist an episode assignment")
    cell = pool.cells[assigned_cell_id]

    executor_handoff = cell.handoff(
        "planner",
        "executor",
        {"schema": "agent-cell-smoke-artifacts/v1", "kind": "plan", "plan": plan, "plan_sha256": _sha256(plan)},
    )
    verifier_handoff = cell.handoff(
        "executor",
        "verifier",
        {"schema": "agent-cell-smoke-artifacts/v1", "kind": "result", "result": result, "result_sha256": _sha256(result)},
    )
    completed = pool.complete_episode(episode_id, "accept")
    persisted = pool.state_manager.load_state(assigned_cell_id)
    if persisted is None:
        raise RuntimeError("CellPool completed without durable state")
    if persisted.get("state") != "idle" or persisted.get("context", {}).get("verdict") != "accept":
        raise RuntimeError(f"unexpected persisted lifecycle state: {persisted.get('state')}")
    if len(persisted.get("handoff_log") or []) != 2:
        raise RuntimeError("CellPool persisted an incomplete handoff chain")

    finished_at = datetime.now(UTC).isoformat()
    receipt = {
        "schema": SCHEMA,
        "smoke_id": f"smoke-{stamp}-{token}",
        "started_at": started_at,
        "finished_at": finished_at,
        "control_plane": "OMO",
        "episode_id": episode_id,
        "cell_id": assigned_cell_id,
        "dispatch_strategy": dispatch.get("strategy"),
        "final_pool_status": pool.get_pool_status(),
        "lifecycle": {
            "dispatch_state": dispatch.get("state"),
            "executor_handoff": executor_handoff.get("schema"),
            "verifier_handoff": verifier_handoff.get("schema"),
            "verdict": completed.get("verdict"),
            "final_state": persisted.get("state"),
            "handoff_count": len(persisted.get("handoff_log") or []),
        },
        "persisted_state_sha256": _sha256(persisted),
        "external_side_effects": "none",
        "value_claim": "NOT_PROVEN",
    }
    stored_receipt = _append_receipt(state_file.parent / "live-smoke-receipts.jsonl", receipt)
    return {
        "schema": SCHEMA,
        "ok": True,
        "episode_id": episode_id,
        "cell_id": assigned_cell_id,
        "state_file": str(state_file),
        "receipt_file": str(state_file.parent / "live-smoke-receipts.jsonl"),
        "receipt_digest": stored_receipt["receipt_digest"],
        "pool_status": pool.get_pool_status(),
        "external_side_effects": "none",
        "value_claim": "NOT_PROVEN",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--state-file",
        type=Path,
        default=DEFAULT_STATE_FILE,
        help="Cell state JSON path (default: canonical OMO runtime state)",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = run_smoke(args.state_file)
    except Exception as exc:
        print(json.dumps({"schema": SCHEMA, "ok": False, "error": str(exc)}, ensure_ascii=False))
        return 1
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(
            f"agent-cell-pool-live-smoke: ok={report['ok']} cell={report['cell_id']} "
            f"receipt={report['receipt_digest']}"
        )
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
