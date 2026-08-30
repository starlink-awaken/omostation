#!/usr/bin/env python3
"""agent-cell-effect-receipt-canary — BET-Y1Q3-T4-05 端到端 honest receipt canary.

验证 Agent Cell 执行者不再用 fixed-success 伪造效果:
  1. 无 admitted workflow context 的 effectful action 返回 effect=not_executed,
     且 target/provider/tool/ledger 零副作用 (文件树快照前后完全一致)。
  2. admitted context 下经 sandbox_tool_runner 执行, 产生 durable receipt
     (ToolInvocationRecorded, external_side_effects=disabled)。
  3. 相同 idempotency identity 重放复用原 receipt, 不重复效果 (invocation_count 恒 1)。
  4. 相同 identity 但 digest 冲突 → 拒绝, 不产生第二个 receipt。
  5. local backend 的 effectful action 一律 not_executed (只保留只读)。
  6. cleanup: 临时 workspace 被回收, 无残留。

用法 (workspace root):
  PYTHONPATH="projects/omo/src" python3 bin/ssot/agent-cell-effect-receipt-canary.py [--json]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import tempfile
from datetime import UTC, datetime, timezone
from pathlib import Path
from typing import Any

EFFECTFUL_ACTION = "generate_doc"
EFFECTFUL_TARGET = "docs/reports/t4-05-canary.md"
CONFLICT_TARGET = "docs/reports/t4-05-canary-conflict.md"
RUN_ID = "run-t4-05-canary"
DISPATCH_ID = "dispatch-t4-05-canary"
WORKER_ID = "worker-t4-05-canary"
ADMISSION_ID = f"adm-{RUN_ID}"
SANDBOX_CAPABILITY = "sandbox.tool.invoke"


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _snapshot_tree(root: Path) -> dict[str, str]:
    """全量文件快照 {相对路径: sha256} — 用于零副作用断言。"""
    if not root.exists():
        return {}
    return {str(p.relative_to(root)): _sha256_file(p) for p in sorted(root.rglob("*")) if p.is_file()}


def _grant(step_run_id: str) -> dict[str, Any]:
    grant: dict[str, Any] = {
        "admission_id": ADMISSION_ID,
        "status": "admitted",
        "workflow_run_id": RUN_ID,
        "trace_id": RUN_ID,
        "backend": "sandbox",
        "step_run_ids": [step_run_id],
        "capabilities": ["execute", SANDBOX_CAPABILITY],
        "policy_digest": "policy-sandbox",
        "request_identity": {
            "packet_id": "WP-BP-0123456789abcdef",
            "packet_hash": "sha256:" + "a" * 64,
            "instruction_binding": {
                "instruction_ref": "repo://docs/operations/blueprint-agent-instruction-pack-v1.md",
                "instruction_version": "blueprint-agent-instruction-pack/v1",
                "content_digest": "sha256:" + "b" * 64,
                "instruction_profile": "executor",
            },
        },
        "issued_at": "2026-08-03T00:00:00Z",
        "expires_at": "2099-01-01T00:00:00Z",
    }
    unsigned = json.dumps(grant, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    grant["proof"] = hashlib.sha256(unsigned.encode()).hexdigest()
    return grant


def _seed_workspace(root: Path) -> None:
    """预置 target/provider/tool/ledger 哨兵 — 零副作用断言的基线客体。"""
    (root / ".omo" / "state").mkdir(parents=True, exist_ok=True)
    (root / ".omo" / "state" / "ledger.jsonl").write_text('{"id": "ledger-baseline"}\n', encoding="utf-8")
    (root / "docs" / "reports").mkdir(parents=True, exist_ok=True)
    (root / "docs" / "reports" / "existing.md").write_text("# baseline\n", encoding="utf-8")
    (root / "provider.json").write_text('{"provider": "baseline"}\n', encoding="utf-8")


def _admitted_context(omo_dir: Path) -> dict[str, str]:
    from omo.worker_lifecycle import (
        acknowledge_worker,
        new_worker_ack_origin_proof,
        record_step_dispatch,
    )
    from omo.workflow_mesh import WorkflowMeshStore, new_workflow_event

    step_run_id = f"{RUN_ID}:execute"
    grant = _grant(step_run_id)
    store = WorkflowMeshStore(omo_dir)
    store.append(
        new_workflow_event(
            "WorkflowRequested",
            RUN_ID,
            trace_id=RUN_ID,
            scene_binding={
                "scene_id": "engineering-delivery",
                "journey_id": "intent-to-evidence",
                "outcome_metric": "verified_delivery_lead_time",
            },
        )
    )
    store.append(new_workflow_event("WorkflowAdmitted", RUN_ID, payload={"admission": grant, **grant}))

    instruction_binding = {
        "instruction_ref": "repo://docs/operations/blueprint-agent-instruction-pack-v1.md",
        "instruction_version": "blueprint-agent-instruction-pack/v1",
        "content_digest": "sha256:" + "b" * 64,
        "instruction_profile": "executor",
    }
    packet_id = "WP-BP-0123456789abcdef"
    packet_hash = "sha256:" + "a" * 64
    origin_proof = new_worker_ack_origin_proof()

    record_step_dispatch(
        omo_dir,
        workflow_run_id=RUN_ID,
        trace_id=RUN_ID,
        dispatch_id=DISPATCH_ID,
        worker_id=WORKER_ID,
        step_run_id=step_run_id,
        admission_id=ADMISSION_ID,
        policy_digest="policy-sandbox",
        packet_id=packet_id,
        packet_hash=packet_hash,
        instruction_binding=instruction_binding,
        ack_origin_proof=origin_proof,
    )
    acknowledge_worker(
        omo_dir,
        workflow_run_id=RUN_ID,
        trace_id=RUN_ID,
        dispatch_id=DISPATCH_ID,
        worker_id=WORKER_ID,
        step_run_id=step_run_id,
        admission_id=ADMISSION_ID,
        packet_id=packet_id,
        packet_hash=packet_hash,
        instruction_binding=instruction_binding,
        origin_proof=origin_proof,
        lease_seconds=3600,
        now=datetime.now(UTC).isoformat(),
    )
    return {
        "workflow_run_id": RUN_ID,
        "trace_id": RUN_ID,
        "dispatch_id": DISPATCH_ID,
        "worker_id": WORKER_ID,
        "step_run_id": step_run_id,
        "admission_id": ADMISSION_ID,
    }


def _invocation_count(omo_dir: Path) -> int:
    from omo.workflow_mesh import WorkflowMeshStore

    return sum(
        1 for event in WorkflowMeshStore(omo_dir).events() if event.get("event_type") == "ToolInvocationRecorded"
    )


def _run_canary() -> dict[str, Any]:
    from omo.resident.executor import Executor

    workspace = Path(tempfile.mkdtemp(prefix="t4-05-canary-"))
    omo_dir = workspace / ".omo"
    steps: list[str] = []
    try:
        _seed_workspace(workspace)

        # ── Step 1: 无 admitted context → not_executed + 零副作用 ──────────
        before = _snapshot_tree(workspace)
        assert before, "预置哨兵必须存在, 否则零副作用断言无意义"

        guardian = Executor(backend="local", omo_dir=omo_dir)
        denied = guardian.execute_task({"action": EFFECTFUL_ACTION, "target": EFFECTFUL_TARGET})
        assert denied.get("effect") == "not_executed", f"预期 not_executed, 实际 {denied.get('effect')}"
        assert denied.get("ok") is False, "无 context 的 effectful action 必须失败"

        after = _snapshot_tree(workspace)
        zero_effect = before == after
        assert zero_effect, f"无 context 的 effectful action 不得产生副作用: {set(after) ^ set(before)}"
        steps.append("no_context_zero_effect")

        # ── Step 2: admitted context → durable receipt ────────────────────
        ctx = _admitted_context(omo_dir)
        executor = Executor(backend="local", omo_dir=omo_dir)
        executed = executor.execute_task(
            {
                "action": EFFECTFUL_ACTION,
                "target": EFFECTFUL_TARGET,
                "admitted_context": ctx,
            }
        )
        assert executed.get("effect") == "executed", f"预期 executed, 实际 {executed}"
        receipt_digest = str(executed.get("receipt_digest") or "")
        assert receipt_digest.startswith("sandbox-invocation:"), f"缺少 durable receipt: {receipt_digest}"
        assert executed.get("replayed") is False, "首次执行不得标记为 replay"
        invocations_after_first = _invocation_count(omo_dir)
        assert invocations_after_first == 1, f"首次执行应产生恰好 1 个 receipt, 实际 {invocations_after_first}"
        steps.append("admitted_context_receipt")

        # ── Step 3: 重放复用原 receipt, 不重复效果 ─────────────────────────
        replay = executor.execute_task(
            {
                "action": EFFECTFUL_ACTION,
                "target": EFFECTFUL_TARGET,
                "admitted_context": ctx,
            }
        )
        assert replay.get("replayed") is True, f"重放必须标记 replayed, 实际 {replay}"
        assert replay.get("receipt_digest") == receipt_digest, "重放必须复用原 receipt digest"
        invocations_after_replay = _invocation_count(omo_dir)
        assert invocations_after_replay == 1, f"重放不得产生第二个 receipt: {invocations_after_replay} != 1"
        steps.append("replay_idempotent")

        # ── Step 4: digest conflict → 拒绝, 不产生第二个 receipt ───────────
        conflict = executor.execute_task(
            {
                "action": EFFECTFUL_ACTION,
                "target": CONFLICT_TARGET,
                "admitted_context": ctx,
            }
        )
        digest_conflict_rejected = conflict.get("effect") == "not_executed" and "sandbox_tool_rejected" in str(
            conflict.get("error", "")
        )
        assert digest_conflict_rejected, f"digest 冲突必须被拒: {conflict}"
        invocations_after_conflict = _invocation_count(omo_dir)
        assert invocations_after_conflict == 1, f"digest 冲突不得产生第二个 receipt: {invocations_after_conflict} != 1"
        steps.append("digest_conflict_rejected")

        # ── Step 5: local backend 只读, effectful 一律 not_executed ────────
        local = Executor(backend="local", omo_dir=omo_dir)
        local_effectful = local.execute_task({"action": "create_draft", "target": "any"})
        assert local_effectful.get("effect") == "not_executed", f"local 必须拒绝 effectful: {local_effectful}"
        read_only = local.execute_task({"action": "query_status", "target": ""})
        assert read_only.get("ok") is True, f"只读操作仍须可用: {read_only}"
        steps.append("local_backend_read_only")

        observed = {
            "no_context_effect": denied["effect"],
            "receipt_digest": receipt_digest,
            "invocations_after_first": invocations_after_first,
            "invocations_after_replay": invocations_after_replay,
            "invocations_after_conflict": invocations_after_conflict,
            "conflict_error": str(conflict.get("error", "")),
        }
    finally:
        # ── Step 6: cleanup ──────────────────────────────────────────────
        shutil.rmtree(workspace, ignore_errors=True)
        steps.append("cleanup")

    return {
        "schema": "agent-cell-effect-receipt-canary/v1",
        "bet_id": "BET-Y1Q3-T4-05",
        "observed_at": datetime.now(UTC).isoformat(),
        "ok": True,
        "zero_effect": True,
        "receipt_backed": True,
        "replay_idempotent": True,
        "digest_conflict_rejected": True,
        "cleanup_done": not workspace.exists(),
        "observed": observed,
        "steps": steps,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    args = parser.parse_args(argv)
    try:
        report = _run_canary()
    except Exception as exc:  # noqa: BLE001 - fail-closed report
        report = {
            "schema": "agent-cell-effect-receipt-canary/v1",
            "bet_id": "BET-Y1Q3-T4-05",
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
        }
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        for key, value in report.items():
            print(f"{key}: {value}")
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
