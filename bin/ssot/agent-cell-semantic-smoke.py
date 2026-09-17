#!/usr/bin/env python3
"""Controlled end-to-end Agent Cell semantic lifecycle canary.

Exercises the persistent OMO pieces behind the Agent Cell design:
RoleRegistry -> CapsuleStore -> Workflow Mesh handoff -> Resident TaskQueue.
The canary performs no provider, filesystem-target, or network side effect.  Its
receipt is a local semantic handoff receipt; it is explicitly not a Claims
Authority receipt and makes no value or completion claim.
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
STATE_DIR = ROOT / ".omo/state/agent-cell/semantic"
SCHEMA = "agent-cell-semantic-smoke/v1"
PLANNER = "role:agent-cell-semantic-planner"
EXECUTOR = "role:agent-cell-semantic-executor"


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical(value)).hexdigest()


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
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


def _read_json_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} root is not an object")
    return value


def _receipt_digest(receipt: dict[str, Any]) -> str:
    payload = {key: value for key, value in receipt.items() if key != "receipt_digest"}
    return _digest(payload)


def _append_receipt(path: Path, receipt: dict[str, Any]) -> dict[str, Any]:
    rows = _load_jsonl(path)
    previous = rows[-1].get("receipt_digest") if rows else None
    candidate = {**receipt, "previous_receipt_digest": previous}
    candidate["receipt_digest"] = _receipt_digest(candidate)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(candidate, ensure_ascii=False, sort_keys=True) + "\n")
    stored = _load_jsonl(path)[-1]
    if _receipt_digest(stored) != stored["receipt_digest"]:
        raise RuntimeError("semantic smoke receipt digest verification failed")
    return stored


def _ensure_role(registry: Any, role_id: str, capability: str) -> Any:
    record = registry.get(role_id)
    if record is None:
        registry.register(role_id, {capability})
        return registry.admit(role_id, expected_version=1)
    if record.admission_state != "admitted" or capability not in record.capabilities:
        raise RuntimeError(f"persistent role {role_id} is not admitted for {capability}")
    return record


def run_smoke() -> dict[str, Any]:
    """Run one verified Role/Capsule/Mesh/Queue lifecycle."""
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    omo_src = ROOT / "projects/omo/src"
    if omo_src.is_dir() and str(omo_src) not in sys.path:
        sys.path.insert(0, str(omo_src))
    try:
        from omo.resident.task_queue import TaskQueue
        from omo.workflow.capsule import CapsuleStore, seal_capsule
        from omo.workflow.role_registry import RoleRegistry
        from omo.workflow_mesh import WorkflowMeshStore, record_capsule_handoff
    except ImportError as exc:
        raise RuntimeError("OMO source is unavailable; initialize projects/omo") from exc

    STATE_DIR.mkdir(parents=True, exist_ok=True)
    registry = RoleRegistry(STATE_DIR / "roles.jsonl")
    planner = _ensure_role(registry, PLANNER, "semantic.plan")
    executor = _ensure_role(registry, EXECUTOR, "semantic.execute")
    if not registry.verify_role(PLANNER, "semantic.plan").allowed:
        raise RuntimeError("planner role admission verification failed")
    if not registry.verify_role(EXECUTOR, "semantic.execute").allowed:
        raise RuntimeError("executor role admission verification failed")

    now = datetime.now(UTC)
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    token = uuid.uuid4().hex[:10]
    run_id = f"semantic-smoke-{stamp}-{token}"
    payload = {
        "schema": "agent-cell-semantic-payload/v1",
        "action": "handoff",
        "external_side_effects": "none",
    }
    payload_digest = _digest(payload)
    local_receipt = {
        "schema": "agent-cell-semantic-receipt/v1",
        "payload_digest": payload_digest,
        "external_side_effects": "none",
    }
    local_receipt_digest = _digest(local_receipt)
    work_packet = {
        "schema": "agent-cell-semantic-work-packet/v1",
        "run_id": run_id,
        "payload_digest": payload_digest,
    }
    capsule = seal_capsule(
        capsule_id=f"capsule:{run_id}",
        bet_id="UNBOUND",
        work_packet_hash=_digest(work_packet),
        receipt_digest=local_receipt_digest,
        producer_role=PLANNER,
        consumer_role=EXECUTOR,
        payload_digest=payload_digest,
    )
    capsule_store = CapsuleStore(STATE_DIR / "capsules.jsonl")
    capsule_store.append(capsule)

    mesh = WorkflowMeshStore(STATE_DIR / ".omo")
    handoff = record_capsule_handoff(mesh, capsule)

    queue = TaskQueue(STATE_DIR / "task-queue.sqlite3", max_queue=32, max_attempts=1)
    task_payload = {
        "capsule_id": capsule.capsule_id,
        "capsule_digest": capsule.digest,
        "payload_digest": payload_digest,
    }
    submitted = queue.submit(
        "bos://agent-cell/semantic-smoke",
        task_payload,
        labels=["agent-cell-semantic-smoke"],
    )
    if not submitted.ok:
        raise RuntimeError(f"semantic task submit failed: {submitted.reason}")
    tasks = queue.poll(limit=1)
    if len(tasks) != 1 or tasks[0].id != submitted.task_id:
        raise RuntimeError("semantic task poll did not return the submitted task")
    completed = queue.complete(submitted.task_id, result={"status": "ok"})
    if not completed:
        raise RuntimeError("semantic task completion failed")

    # Reload every durable store and verify the persisted lifecycle, not only
    # the in-memory objects used to create it.
    roles = RoleRegistry(STATE_DIR / "roles.jsonl")
    capsules = CapsuleStore(STATE_DIR / "capsules.jsonl")
    reloaded_capsule = capsules.get(capsule.capsule_id)
    reloaded_mesh = WorkflowMeshStore(STATE_DIR / ".omo")
    handoff_events = [
        event
        for event in reloaded_mesh.events()
        if event.get("payload", {}).get("handoff", {}).get("capsule", {}).get("capsule_id")
        == capsule.capsule_id
    ]
    persisted_task = TaskQueue(STATE_DIR / "task-queue.sqlite3").get(submitted.task_id)
    ok = bool(
        roles.verify_role(PLANNER, "semantic.plan").allowed
        and roles.verify_role(EXECUTOR, "semantic.execute").allowed
        and reloaded_capsule is not None
        and reloaded_capsule.digest == capsule.digest
        and len(handoff_events) == 1
        and persisted_task is not None
        and persisted_task.status.value == "completed"
        and persisted_task.result == {"status": "ok"}
    )
    if not ok:
        raise RuntimeError("reloaded semantic lifecycle verification failed")

    receipt = {
        "schema": SCHEMA,
        "run_id": run_id,
        "started_at": now.isoformat(),
        "finished_at": datetime.now(UTC).isoformat(),
        "roles": {
            "planner": {"role_id": PLANNER, "version": planner.version, "digest": planner.digest},
            "executor": {"role_id": EXECUTOR, "version": executor.version, "digest": executor.digest},
        },
        "capsule": {
            "capsule_id": capsule.capsule_id,
            "digest": capsule.digest,
            "payload_digest": payload_digest,
            "receipt_digest": local_receipt_digest,
        },
        "mesh": {
            "handoff_id": handoff["handoff_id"],
            "event_count": len(handoff_events),
            "event_digest": _digest(handoff_events[0]),
        },
        "queue": {
            "task_id": submitted.task_id,
            "status": persisted_task.status.value,
            "result": persisted_task.result,
        },
        "claims_authority_invoked": False,
        "claim_authority_receipt": "NOT_USED",
        "external_side_effects": "none",
        "value_claim": "NOT_PROVEN",
    }
    stored_receipt = _append_receipt(STATE_DIR / "semantic-smoke-receipts.jsonl", receipt)
    return {
        "schema": SCHEMA,
        "ok": True,
        "run_id": run_id,
        "state_dir": str(STATE_DIR),
        "capsule_id": capsule.capsule_id,
        "task_id": submitted.task_id,
        "receipt_digest": stored_receipt["receipt_digest"],
        "claims_authority_invoked": False,
        "external_side_effects": "none",
        "value_claim": "NOT_PROVEN",
    }


def verify_latest() -> dict[str, Any]:
    """Verify the durable receipt chain and latest cross-store bindings."""
    receipts = _load_jsonl(STATE_DIR / "semantic-smoke-receipts.jsonl")
    if not receipts:
        return {"schema": SCHEMA, "ok": True, "verdict": "EMPTY", "receipt_count": 0}
    try:
        from omo.resident.task_queue import TaskQueue
        from omo.workflow.capsule import CapsuleStore
        from omo.workflow.role_registry import RoleRegistry
        from omo.workflow_mesh import WorkflowMeshStore
    except ImportError as exc:
        return {
            "schema": SCHEMA,
            "ok": False,
            "verdict": "UNAVAILABLE",
            "receipt_count": len(receipts),
            "error": f"OMO source unavailable: {type(exc).__name__}",
        }
    roles_path = STATE_DIR / "roles.jsonl"
    capsules_path = STATE_DIR / "capsules.jsonl"
    queue_path = STATE_DIR / "task-queue.sqlite3"
    roles = RoleRegistry(roles_path)
    capsules = CapsuleStore(capsules_path)
    queue = TaskQueue(queue_path)
    mesh = WorkflowMeshStore(STATE_DIR / ".omo")
    mesh_events = mesh.events()
    capsules_by_id = {record.capsule_id: record for record in capsules.list()}
    previous = None
    chain_ok = True
    digests_ok = True
    bindings_ok = True
    lifecycle_ok = True
    for receipt in receipts:
        if _receipt_digest(receipt) != receipt.get("receipt_digest"):
            digests_ok = False
        if receipt.get("previous_receipt_digest") != previous:
            chain_ok = False
        previous = receipt.get("receipt_digest")
        if receipt.get("schema") != SCHEMA:
            lifecycle_ok = False
        role_report = receipt.get("roles") if isinstance(receipt.get("roles"), dict) else {}
        for role_id, capability, key in (
            (PLANNER, "semantic.plan", "planner"),
            (EXECUTOR, "semantic.execute", "executor"),
        ):
            expected = role_report.get(key) if isinstance(role_report.get(key), dict) else {}
            record = roles.get(role_id)
            verification = roles.verify_role(role_id, capability)
            if not (
                record is not None
                and verification.allowed
                and expected.get("version") == record.version
                and expected.get("digest") == record.digest
            ):
                bindings_ok = False

        capsule_id = receipt.get("capsule", {}).get("capsule_id") if isinstance(receipt.get("capsule"), dict) else None
        expected_capsule = capsules_by_id.get(capsule_id)
        receipt_capsule = receipt.get("capsule") if isinstance(receipt.get("capsule"), dict) else {}
        if not (
            expected_capsule is not None
            and receipt_capsule.get("digest") == expected_capsule.digest
            and receipt_capsule.get("payload_digest") == expected_capsule.payload_digest
            and receipt_capsule.get("receipt_digest") == expected_capsule.receipt_digest
        ):
            bindings_ok = False
        matching_events = [
            event
            for event in mesh_events
            if event.get("payload", {}).get("handoff", {}).get("capsule", {}).get("capsule_id")
            == capsule_id
        ]
        mesh_report = receipt.get("mesh") if isinstance(receipt.get("mesh"), dict) else {}
        if not (
            len(matching_events) == 1
            and mesh_report.get("event_count") == 1
            and mesh_report.get("event_digest") == _digest(matching_events[0])
            and mesh_report.get("handoff_id")
        ):
            bindings_ok = False
        queue_report = receipt.get("queue") if isinstance(receipt.get("queue"), dict) else {}
        task = queue.get(queue_report.get("task_id"))
        if not (
            task is not None
            and task.status.value == "completed"
            and task.result == {"status": "ok"}
            and queue_report.get("status") == "completed"
            and queue_report.get("result") == {"status": "ok"}
        ):
            bindings_ok = False
        if not (
            receipt.get("claims_authority_invoked") is False
            and receipt.get("claim_authority_receipt") == "NOT_USED"
            and receipt.get("external_side_effects") == "none"
            and receipt.get("value_claim") == "NOT_PROVEN"
        ):
            lifecycle_ok = False
    latest = receipts[-1]
    ok = digests_ok and chain_ok and bindings_ok and lifecycle_ok
    return {
        "schema": SCHEMA,
        "receipt_count": len(receipts),
        "state_count": len(roles.list()) + len(capsules.list()),
        "role_bindings_ok": bindings_ok,
        "capsule_bindings_ok": bindings_ok,
        "mesh_bindings_ok": bindings_ok,
        "queue_bindings_ok": bindings_ok,
        "digests_ok": digests_ok,
        "chain_ok": chain_ok,
        "bindings_ok": bindings_ok,
        "lifecycle_ok": lifecycle_ok,
        "ok": ok,
        "verdict": "PASS" if ok else "FAILED",
        "latest_run_id": latest.get("run_id"),
        "latest_receipt_digest": latest.get("receipt_digest"),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify", action="store_true", help="Verify durable receipt chain only")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = verify_latest() if args.verify else run_smoke()
    except Exception as exc:
        print(json.dumps({"schema": SCHEMA, "ok": False, "error": str(exc)}, ensure_ascii=False))
        return 1
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"agent-cell-semantic-smoke: ok={report['ok']} verdict={report.get('verdict', 'RUN')}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
