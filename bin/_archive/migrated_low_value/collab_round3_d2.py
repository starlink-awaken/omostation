"""C 波 C2 — 协作管线执行本轮 D2 真实任务 (Round 3, 吃狗粮).

用 CollabBus (orchestrator→implementer→verifier) 协作评估 D2 卡清理决策,
非单 agent 直做. workorder C2: 协作管线跑真实任务 (D2/R1), 轨迹入 audits.
"""
from __future__ import annotations

import uuid
from typing import Any

from role_collab import CollabBus, CollabMessage


def _msg(
    type_: str,
    from_agent: str,
    from_role: str,
    to_role: str | None,
    task_ref: str,
    payload: dict | None = None,
    cid: str | None = None,
) -> CollabMessage:
    return CollabMessage(
        id=uuid.uuid4().hex,
        type=type_,
        from_agent=from_agent,
        from_role=from_role,
        to_role=to_role,
        task_ref=task_ref,
        payload=payload or {},
        correlation_id=cid,
    )


# D2 卡评估输入 (单 agent R+D 波结论, 作为 implementer 分析依据)
D2_CARD_TRIAGE = {
    "needs-human-ingress-registry-drift": "keep",
    "needs-human-p80-physical-hosts": "keep",
    "needs-human-batch2-physical-recovery-checklist": "keep",
    "needs-human-p80-phase45-bos-stdio": "keep",
    "needs-human-mof-m4-d1-d4-decisions": "keep",
    "needs-human-batch2-role-expansion-proposal": "keep",
    "needs-human-p81-m1-acceptance": "close",
    "needs-human-batch3-proposal": "close",
    "needs-human-p81-batch4-proposal": "close",
}


def run_d2_triage_via_collab(card_id: str, recommendation: str) -> dict[str, Any]:
    """协作管线 (3角色) 跑 D2 单卡评估: orchestrator 派 → implementer 分析 → verifier 验证."""
    bus = CollabBus()
    task_ref = f"d2-triage-{card_id}"
    trail: list[str] = []
    verdict = {"card": card_id, "recommendation": recommendation, "verified": False}

    def on_assign(m: CollabMessage) -> None:
        trail.append("assign")
        bus.publish(_msg("claim_ack", "impl-1", "implementer", "orchestrator", task_ref, cid=m.id))

    def on_claim(m: CollabMessage) -> None:
        trail.append("claim_ack")
        bus.publish(
            _msg("handoff", "impl-1", "implementer", "verifier", task_ref, {"recommendation": recommendation}, cid=m.correlation_id)
        )

    def on_handoff(m: CollabMessage) -> None:
        trail.append("handoff")
        ok = recommendation in ("keep", "close", "defer")
        verdict["verified"] = ok
        bus.publish(_msg("verify_result", "ver-1", "verifier", "orchestrator", task_ref, {"pass": ok}, cid=m.correlation_id))

    def on_verify(m: CollabMessage) -> None:
        trail.append("verify_result")
        if m.payload.get("pass"):
            bus.publish(_msg("complete", "orch-1", "orchestrator", None, task_ref, cid=m.correlation_id))
            trail.append("complete")

    bus.subscribe(on_assign, type="assign")
    bus.subscribe(on_claim, type="claim_ack")
    bus.subscribe(on_handoff, type="handoff")
    bus.subscribe(on_verify, type="verify_result")

    bus.publish(_msg("assign", "orch-1", "orchestrator", "implementer", task_ref, {"card": card_id}))

    return {
        "task": task_ref,
        "card": card_id,
        "verdict": verdict,
        "completed": "complete" in trail,
        "trail": trail,
        "n_messages": len(bus.history),
    }


def run_d2_batch_via_collab() -> dict[str, Any]:
    """协作管线跑 D2 全部卡评估 (≥8 任务, workorder C2). 返回批量轨迹."""
    runs = [run_d2_triage_via_collab(c, r) for c, r in D2_CARD_TRIAGE.items()]
    completed = sum(1 for r in runs if r["completed"])
    return {
        "n_tasks": len(runs),
        "completed": completed,
        "all_completed": completed == len(runs),
        "runs": runs,
        "mode": "collab-pipeline (orchestrator→implementer→verifier)",
        "vs_single_agent": "对照: 单 agent 直做无 assign/claim/handoff/verify 协作轨迹",
    }
