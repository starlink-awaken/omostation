"""STRAT-P81 Batch1 B1 — Role framework (3 first-ship roles + protocol).

Maps engineering / governance / audit onto capability sets and collab message
boundaries (G-DEL.2a contract). Process-local only.
"""
from __future__ import annotations

import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# First-ship roles (workorder B1 suggestion)
ROLE_ENGINEERING = "engineering"
ROLE_GOVERNANCE = "governance"
ROLE_AUDIT = "audit"

FIRST_SHIP_ROLES = (ROLE_ENGINEERING, ROLE_GOVERNANCE, ROLE_AUDIT)

# Second-wave roles (Batch3 C1 expansion — research/delivery, ADR-0235)
ROLE_RESEARCH = "research"
ROLE_DELIVERY = "delivery"

SECOND_WAVE_ROLES = (ROLE_RESEARCH, ROLE_DELIVERY)
ALL_ROLES = FIRST_SHIP_ROLES + SECOND_WAVE_ROLES

# Map to legacy G-DEL.2a role ids used by CollabBus handshake
LEGACY_ROLE_MAP = {
    ROLE_ENGINEERING: "implementer",
    ROLE_GOVERNANCE: "orchestrator",
    ROLE_AUDIT: "verifier",
    ROLE_RESEARCH: "researcher",
    ROLE_DELIVERY: "deliverer",
}

MessageHandler = Callable[["RoleMessage"], None]


@dataclass(frozen=True)
class RoleSpec:
    role_id: str
    display_name: str
    capabilities: tuple[str, ...]
    can_send: tuple[str, ...]
    can_recv: tuple[str, ...]
    private_scope_prefix: str


ROLE_CATALOG: dict[str, RoleSpec] = {
    ROLE_ENGINEERING: RoleSpec(
        role_id=ROLE_ENGINEERING,
        display_name="Engineering",
        capabilities=("write-code", "run-tests", "claim-path", "handoff"),
        can_send=("claim_ack", "progress", "handoff", "block"),
        can_recv=("assign", "verify_result", "complete"),
        private_scope_prefix="private.engineering",
    ),
    ROLE_GOVERNANCE: RoleSpec(
        role_id=ROLE_GOVERNANCE,
        display_name="Governance",
        # C1: 加 dispatch-research/dispatch-delivery 派发二波角色 (不破坏现有 3 角色协议)
        capabilities=(
            "assign",
            "claim-path",
            "write-adr",
            "closeout",
            "dispatch-research",
            "dispatch-delivery",
        ),
        can_send=(
            "assign",
            "complete",
            "progress",
            "block",
            "research_request",
            "delivery_request",
        ),
        can_recv=(
            "claim_ack",
            "handoff",
            "verify_result",
            "block",
            "progress",
            "research_result",
            "delivery_registered",
        ),
        private_scope_prefix="private.governance",
    ),
    ROLE_AUDIT: RoleSpec(
        role_id=ROLE_AUDIT,
        display_name="Audit",
        capabilities=("verify", "read-evidence", "write-audit"),
        can_send=("verify_result", "progress", "block"),
        can_recv=("handoff", "assign", "complete"),
        private_scope_prefix="private.audit",
    ),
    # Second-wave roles (Batch3 C1, ADR-0235): read-only knowledge + delivery projection
    ROLE_RESEARCH: RoleSpec(
        role_id=ROLE_RESEARCH,
        display_name="Research",
        # Read-only 知识面: KOS 检索/文献合成, 不可 claim 代码路径 (eval 页边界)
        capabilities=("read-evidence", "search-kos", "synthesize-knowledge"),
        can_send=("research_result", "progress", "block"),
        can_recv=("assign", "research_request", "verify_result"),
        private_scope_prefix="private.research",
    ),
    ROLE_DELIVERY: RoleSpec(
        role_id=ROLE_DELIVERY,
        display_name="Delivery",
        # 只写 delivery/X3 投影: 交付卡登记, 无代码写权 (eval 页边界, 凑数已禁)
        capabilities=(
            "register-delivery",
            "write-x3-projection",
            "closeout-delivery",
        ),
        can_send=("delivery_registered", "progress", "block"),
        can_recv=("assign", "delivery_request", "complete"),
        private_scope_prefix="private.delivery",
    ),
}


@dataclass
class RoleInstance:
    agent_id: str
    role_id: str
    created_at: float = field(default_factory=time.time)
    active: bool = True

    @property
    def spec(self) -> RoleSpec:
        return ROLE_CATALOG[self.role_id]


class RoleRegistry:
    """Register / load / switch role instances."""

    def __init__(self) -> None:
        self._instances: dict[str, RoleInstance] = {}

    def register(self, role_id: str, *, agent_id: str | None = None) -> RoleInstance:
        if role_id not in ROLE_CATALOG:
            raise ValueError(f"unknown role_id: {role_id}")
        aid = agent_id or f"{role_id}-{uuid.uuid4().hex[:8]}"
        if aid in self._instances:
            raise ValueError(f"agent already registered: {aid}")
        inst = RoleInstance(agent_id=aid, role_id=role_id)
        self._instances[aid] = inst
        return inst

    def load(self, agent_id: str) -> RoleInstance:
        if agent_id not in self._instances:
            raise KeyError(agent_id)
        return self._instances[agent_id]

    def switch(self, agent_id: str, new_role_id: str) -> RoleInstance:
        if new_role_id not in ROLE_CATALOG:
            raise ValueError(f"unknown role_id: {new_role_id}")
        old = self.load(agent_id)
        old.active = False
        inst = RoleInstance(agent_id=agent_id, role_id=new_role_id)
        self._instances[agent_id] = inst
        return inst

    def list_by_role(self, role_id: str) -> list[RoleInstance]:
        return [i for i in self._instances.values() if i.role_id == role_id and i.active]


@dataclass
class RoleMessage:
    id: str
    type: str
    from_agent: str
    from_role: str
    to_role: str | None
    task_ref: str
    payload: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    correlation_id: str | None = None


class RoleProtocolBus:
    """Collab protocol with send/recv boundary enforcement."""

    def __init__(self, registry: RoleRegistry | None = None) -> None:
        self.registry = registry or RoleRegistry()
        self.history: list[RoleMessage] = []
        self._subs: list[tuple[dict[str, str | None], MessageHandler]] = []

    def subscribe(
        self,
        handler: MessageHandler,
        *,
        role_id: str | None = None,
        type: str | None = None,
    ) -> None:
        self._subs.append(({"role_id": role_id, "type": type}, handler))

    def publish(self, msg: RoleMessage, *, enforce: bool = True) -> None:
        if enforce:
            spec = ROLE_CATALOG.get(msg.from_role)
            if spec is None:
                raise ValueError(f"unknown from_role: {msg.from_role}")
            if msg.type not in spec.can_send:
                raise PermissionError(
                    f"role {msg.from_role} cannot send type={msg.type}"
                )
            if msg.to_role:
                to_spec = ROLE_CATALOG.get(msg.to_role)
                if to_spec is None:
                    raise ValueError(f"unknown to_role: {msg.to_role}")
                if msg.type not in to_spec.can_recv:
                    raise PermissionError(
                        f"role {msg.to_role} cannot recv type={msg.type}"
                    )
        self.history.append(msg)
        for filt, handler in self._subs:
            if filt["type"] and filt["type"] != msg.type:
                continue
            if (
                filt["role_id"]
                and msg.to_role is not None
                and filt["role_id"] != msg.to_role
            ):
                continue
            handler(msg)

    def replay(self) -> list[dict[str, Any]]:
        return [
            {
                "id": m.id,
                "type": m.type,
                "from_role": m.from_role,
                "to_role": m.to_role,
                "task_ref": m.task_ref,
                "payload": m.payload,
            }
            for m in self.history
        ]


def _agent_suffix(task_ref: str) -> str:
    """Stable short suffix for agent ids (keep within yaml-safe length)."""
    cleaned = "".join(c if c.isalnum() or c in "-_" else "-" for c in task_ref)
    return cleaned[:12] or "task"


def _run_collab_handshake(
    *,
    task_ref: str,
    assign_payload: dict[str, Any],
    claim_payload: dict[str, Any] | None = None,
    handoff_payload: dict[str, Any] | None = None,
    complete_payload: dict[str, Any] | None = None,
    fail_verify: bool = False,
    verify_extra: Callable[[], dict[str, Any]] | None = None,
    bus: RoleProtocolBus | None = None,
) -> dict[str, Any]:
    """Shared assign→claim_ack→handoff→verify_result→complete pipeline.

    ``verify_extra`` may return ``{"pass": bool, ...}`` merged into verify payload;
    if it returns ``pass=False``, handshake fails even when ``fail_verify`` is False.
    """
    bus = bus or RoleProtocolBus()
    reg = bus.registry
    suffix = _agent_suffix(task_ref)
    eng = reg.register(ROLE_ENGINEERING, agent_id=f"eng-{suffix}")
    gov = reg.register(ROLE_GOVERNANCE, agent_id=f"gov-{suffix}")
    aud = reg.register(ROLE_AUDIT, agent_id=f"aud-{suffix}")
    steps: list[str] = []
    state: dict[str, Any] = {}

    def on_assign(m: RoleMessage) -> None:
        steps.append("assign")
        bus.publish(
            RoleMessage(
                id=uuid.uuid4().hex,
                type="claim_ack",
                from_agent=eng.agent_id,
                from_role=ROLE_ENGINEERING,
                to_role=ROLE_GOVERNANCE,
                task_ref=task_ref,
                payload=dict(claim_payload or {}),
                correlation_id=m.id,
            )
        )

    def on_claim(m: RoleMessage) -> None:
        steps.append("claim_ack")
        bus.publish(
            RoleMessage(
                id=uuid.uuid4().hex,
                type="handoff",
                from_agent=eng.agent_id,
                from_role=ROLE_ENGINEERING,
                to_role=ROLE_AUDIT,
                task_ref=task_ref,
                payload=dict(handoff_payload or {"evidence": "ok"}),
                correlation_id=m.correlation_id or m.id,
            )
        )

    def on_handoff(m: RoleMessage) -> None:
        steps.append("handoff")
        ok = not fail_verify
        extra: dict[str, Any] = {}
        if verify_extra is not None:
            extra = verify_extra() or {}
            if "pass" in extra:
                ok = ok and bool(extra["pass"])
        state["verify"] = ok
        payload = {"pass": ok, **{k: v for k, v in extra.items() if k != "pass"}}
        bus.publish(
            RoleMessage(
                id=uuid.uuid4().hex,
                type="verify_result",
                from_agent=aud.agent_id,
                from_role=ROLE_AUDIT,
                to_role=ROLE_GOVERNANCE,
                task_ref=task_ref,
                payload=payload,
                correlation_id=m.correlation_id,
            )
        )

    def on_verify(m: RoleMessage) -> None:
        steps.append("verify_result")
        if m.payload.get("pass"):
            bus.publish(
                RoleMessage(
                    id=uuid.uuid4().hex,
                    type="complete",
                    from_agent=gov.agent_id,
                    from_role=ROLE_GOVERNANCE,
                    to_role=None,
                    task_ref=task_ref,
                    payload=dict(complete_payload or {}),
                    correlation_id=m.correlation_id,
                )
            )
            steps.append("complete")

    bus.subscribe(on_assign, type="assign")
    bus.subscribe(on_claim, type="claim_ack")
    bus.subscribe(on_handoff, type="handoff")
    bus.subscribe(on_verify, type="verify_result")

    bus.publish(
        RoleMessage(
            id=uuid.uuid4().hex,
            type="assign",
            from_agent=gov.agent_id,
            from_role=ROLE_GOVERNANCE,
            to_role=ROLE_ENGINEERING,
            task_ref=task_ref,
            payload=dict(assign_payload),
        )
    )

    completed = "complete" in steps and state.get("verify") is True
    return {
        "task_ref": task_ref,
        "completed": completed,
        "steps": steps,
        "replay": bus.replay(),
        "roles": [eng.role_id, gov.role_id, aud.role_id],
        "error": None if completed else "handshake_incomplete",
        "bus": bus,
    }


def run_three_role_handshake(
    bus: RoleProtocolBus | None = None,
    *,
    fail_verify: bool = False,
) -> dict[str, Any]:
    """Full assign→claim→handoff→verify→complete across 3 first-ship roles."""
    task_ref = f"batch1-task-{uuid.uuid4().hex[:8]}"
    result = _run_collab_handshake(
        task_ref=task_ref,
        assign_payload={"kpi": "batch1-collab"},
        fail_verify=fail_verify,
        bus=bus,
    )
    result.pop("bus", None)
    return result


def measure_three_role_batch(
    *, n_tasks: int = 30, inject_fail_every: int = 0
) -> dict[str, Any]:
    """G-DEL.2b-style batch measure for 3 first-ship roles.

    Note: ``meets_gate`` from ``stamp_non_physical_goal`` means *process-local*
    protocol success only — not official G-DEL.2b human announce.
    """
    from caliber import stamp_non_physical_goal

    ok = 0
    trails: list[dict[str, Any]] = []
    for i in range(n_tasks):
        fail = inject_fail_every > 0 and (i % inject_fail_every == 0)
        r = run_three_role_handshake(fail_verify=fail)
        if r["completed"]:
            ok += 1
        trails.append(
            {
                "task_ref": r["task_ref"],
                "completed": r["completed"],
                "steps": r["steps"],
            }
        )
    rate = ok / n_tasks if n_tasks else 0.0
    stamped = stamp_non_physical_goal(
        {
            "n_tasks": n_tasks,
            "completed": ok,
            "completion_rate": rate,
            "completion_rate_pct": round(rate * 100, 4),
            "gate": "G-DEL.2b",
            "kpi": "3-role collab completion > 95%",
            "env": "process-local RoleProtocolBus (Batch1 B1-B4)",
            "roles": list(FIRST_SHIP_ROLES),
            "trails_sample": trails[:5],
            "trails_all_count": len(trails),
            "official_announce": False,
        },
        ok=rate > 0.95,
    )
    # Explicit: process-local gate must never flip physical
    stamped["meets_physical_gate"] = False
    return stamped


def run_backlog_collab(
    *,
    task_id: str,
    task_path: str,
    title: str = "",
    work_summary: str = "",
    fail_verify: bool = False,
    require_path_exists: bool = True,
) -> dict[str, Any]:
    """Run 3-role collab bound to a **real** backlog task id/path (Batch1 B2).

    Unlike synthetic ``run_three_role_handshake`` (auto UUID task_ref), this uses
    the backlog ``task_id`` as ``task_ref`` and records path + handoff evidence
    in the protocol payload for audit trails.
    """
    if not task_id or not task_path:
        raise ValueError("task_id and task_path required for real backlog collab")

    handoff_evidence = {
        "task_id": task_id,
        "task_path": task_path,
        "title": title or task_id,
        "work_summary": work_summary
        or f"3-role collab review on backlog item {task_id}",
        "artifacts": [task_path],
    }

    def verify_extra() -> dict[str, Any]:
        path = Path(task_path)
        # Prefer is_file: remediation cards are files; bare exists() allows dirs
        path_ok = path.is_file()
        if not require_path_exists:
            path_ok = True
        return {
            "pass": path_ok,
            "task_path": task_path,
            "path_exists": path.is_file() or path.exists(),
            "path_is_file": path.is_file(),
            "evidence_keys": list(handoff_evidence.keys()),
        }

    result = _run_collab_handshake(
        task_ref=task_id,
        assign_payload={
            "kpi": "real-backlog-collab",
            "task_id": task_id,
            "task_path": task_path,
            "title": title,
        },
        claim_payload={"claimed_path": task_path},
        handoff_payload={"evidence": handoff_evidence},
        complete_payload={"task_path": task_path, "closed": True},
        fail_verify=fail_verify,
        verify_extra=verify_extra,
    )
    result.pop("bus", None)
    if not result["completed"] and require_path_exists:
        result["error"] = "handshake_incomplete_or_path_missing"
    return {
        **result,
        "task_id": task_id,
        "task_path": task_path,
        "title": title,
        "handoff_evidence": handoff_evidence,
    }


# ─── C2: collaboration protocol deepening (Batch3, ADR-0236) ───


def run_multi_round_negotiation(
    bus: RoleProtocolBus | None = None,
    *,
    task_ref: str | None = None,
    max_rounds: int = 3,
    satisfy_after: int = 2,
) -> dict[str, Any]:
    """C2 多轮协商握手 (governance ↔ research).

    governance 发 research_request → research 回 research_result. 若 governance
    未满意 (round < satisfy_after) 再追问. 比单向 assign→handshake→verify 更深:
    允许基于研究结果多轮调整 (ADR-0236).
    """
    bus = bus or RoleProtocolBus()
    reg = bus.registry
    task_ref = task_ref or f"c2-nego-{uuid.uuid4().hex[:8]}"
    gov = reg.register(ROLE_GOVERNANCE, agent_id=f"gov-{_agent_suffix(task_ref)}")
    res = reg.register(ROLE_RESEARCH, agent_id=f"res-{_agent_suffix(task_ref)}")
    log: list[dict[str, Any]] = []
    satisfied = False
    for rnd in range(1, max_rounds + 1):
        req = RoleMessage(
            id=uuid.uuid4().hex,
            type="research_request",
            from_agent=gov.agent_id,
            from_role=ROLE_GOVERNANCE,
            to_role=ROLE_RESEARCH,
            task_ref=task_ref,
            payload={"round": rnd, "query": f"research round {rnd}"},
        )
        bus.publish(req)
        result = RoleMessage(
            id=uuid.uuid4().hex,
            type="research_result",
            from_agent=res.agent_id,
            from_role=ROLE_RESEARCH,
            to_role=ROLE_GOVERNANCE,
            task_ref=task_ref,
            payload={"round": rnd, "findings": f"result round {rnd}"},
            correlation_id=req.id,
        )
        bus.publish(result)
        log.append({"round": rnd, "request": req.id, "result": result.id})
        if rnd >= satisfy_after:
            satisfied = True
            break
    return {
        "task_ref": task_ref,
        "rounds_executed": len(log),
        "satisfied": satisfied,
        "negotiation_log": log,
        "roles": [ROLE_GOVERNANCE, ROLE_RESEARCH],
    }


# Conflict resolution precedence (low → high): governance 仲裁, audit 证据优先
_CONFLICT_PRECEDENCE = (
    ROLE_RESEARCH,
    ROLE_DELIVERY,
    ROLE_ENGINEERING,
    ROLE_AUDIT,
    ROLE_GOVERNANCE,
)


def resolve_message_conflict(messages: list[RoleMessage]) -> RoleMessage | None:
    """C2 冲突消解: 同一 task_ref+type 多角色消息, 按角色优先级取胜者.

    research < delivery < engineering < audit < governance.
    governance 可仲裁; audit 证据优先于实现. Returns None if input empty.
    """
    if not messages:
        return None
    return max(
        messages,
        key=lambda m: _CONFLICT_PRECEDENCE.index(m.from_role)
        if m.from_role in _CONFLICT_PRECEDENCE
        else -1,
    )


def decompose_into_subtasks(
    task_ref: str,
    subtask_refs: list[str],
) -> dict[str, Any]:
    """C2 任务分解: 大任务 → 子任务列表, 每个子任务走 3-role handshake 再组合.

    子任务用 run_backlog_collab 骨架 (require_path_exists=False 避免 path 依赖).
    Returns per-subtask completion + aggregate rate.
    """
    results: list[dict[str, Any]] = []
    completed = 0
    for sub in subtask_refs:
        r = run_backlog_collab(
            task_id=sub,
            task_path=f"decomposed://{task_ref}/{sub}",
            title=f"subtask {sub} of {task_ref}",
            require_path_exists=False,
        )
        results.append({"subtask": sub, "completed": r["completed"]})
        if r["completed"]:
            completed += 1
    total = len(subtask_refs) or 1
    return {
        "task_ref": task_ref,
        "subtasks": results,
        "completed": completed,
        "total": len(subtask_refs),
        "aggregate_rate": completed / total,
    }


# ─── C1 deepening: 5-role collaboration batch (P1, ADR-0235 扩容验证) ───


def run_five_role_handshake(
    bus: RoleProtocolBus | None = None,
    *,
    fail_verify: bool = False,
) -> dict[str, Any]:
    """5 角色 dispatch 流 (C1 扩容验证, ADR-0235).

    governance 主导 dispatch 全 5 角色:
      gov→research: research_request → research→gov: research_result
      gov→delivery: delivery_request → delivery→gov: delivery_registered
      gov→engineering: assign → eng→gov: claim_ack → eng→audit: handoff
      audit→gov: verify_result → gov: complete

    比 3 角色 handshake 多了 research/delivery 二波角色参与 (知识合成 + 交付投影),
    验证 C1 扩容后 5 角色协作边界 (can_send/can_recv) 全链路合法.
    """
    bus = bus or RoleProtocolBus()
    reg = bus.registry
    task_ref = f"c1-five-{uuid.uuid4().hex[:8]}"
    suffix = _agent_suffix(task_ref)
    gov = reg.register(ROLE_GOVERNANCE, agent_id=f"gov-{suffix}")
    res = reg.register(ROLE_RESEARCH, agent_id=f"res-{suffix}")
    dly = reg.register(ROLE_DELIVERY, agent_id=f"dly-{suffix}")
    eng = reg.register(ROLE_ENGINEERING, agent_id=f"eng-{suffix}")
    aud = reg.register(ROLE_AUDIT, agent_id=f"aud-{suffix}")
    steps: list[str] = []
    state: dict[str, Any] = {}

    def on_research_request(m: RoleMessage) -> None:
        steps.append("research_request")
        bus.publish(RoleMessage(
            id=uuid.uuid4().hex, type="research_result",
            from_agent=res.agent_id, from_role=ROLE_RESEARCH, to_role=ROLE_GOVERNANCE,
            task_ref=task_ref, payload={"findings": "research synthesized"},
            correlation_id=m.id,
        ))

    def on_research_result(m: RoleMessage) -> None:
        steps.append("research_result")
        bus.publish(RoleMessage(
            id=uuid.uuid4().hex, type="delivery_request",
            from_agent=gov.agent_id, from_role=ROLE_GOVERNANCE, to_role=ROLE_DELIVERY,
            task_ref=task_ref, payload={"deliverable": "x3 projection"},
            correlation_id=m.id,
        ))

    def on_delivery_request(m: RoleMessage) -> None:
        steps.append("delivery_request")
        bus.publish(RoleMessage(
            id=uuid.uuid4().hex, type="delivery_registered",
            from_agent=dly.agent_id, from_role=ROLE_DELIVERY, to_role=ROLE_GOVERNANCE,
            task_ref=task_ref, payload={"registered": True},
            correlation_id=m.id,
        ))

    def on_delivery_registered(m: RoleMessage) -> None:
        steps.append("delivery_registered")
        bus.publish(RoleMessage(
            id=uuid.uuid4().hex, type="assign",
            from_agent=gov.agent_id, from_role=ROLE_GOVERNANCE, to_role=ROLE_ENGINEERING,
            task_ref=task_ref, payload={"kpi": "five-role"},
            correlation_id=m.id,
        ))

    def on_assign(m: RoleMessage) -> None:
        steps.append("assign")
        bus.publish(RoleMessage(
            id=uuid.uuid4().hex, type="claim_ack",
            from_agent=eng.agent_id, from_role=ROLE_ENGINEERING, to_role=ROLE_GOVERNANCE,
            task_ref=task_ref, payload={"claimed": True},
            correlation_id=m.id,
        ))

    def on_claim_ack(m: RoleMessage) -> None:
        steps.append("claim_ack")
        bus.publish(RoleMessage(
            id=uuid.uuid4().hex, type="handoff",
            from_agent=eng.agent_id, from_role=ROLE_ENGINEERING, to_role=ROLE_AUDIT,
            task_ref=task_ref, payload={"evidence": "implemented"},
            correlation_id=m.id,
        ))

    def on_handoff(m: RoleMessage) -> None:
        steps.append("handoff")
        ok = not fail_verify
        state["verify"] = ok
        bus.publish(RoleMessage(
            id=uuid.uuid4().hex, type="verify_result",
            from_agent=aud.agent_id, from_role=ROLE_AUDIT, to_role=ROLE_GOVERNANCE,
            task_ref=task_ref, payload={"pass": ok},
            correlation_id=m.id,
        ))

    def on_verify(m: RoleMessage) -> None:
        steps.append("verify_result")
        if m.payload.get("pass"):
            bus.publish(RoleMessage(
                id=uuid.uuid4().hex, type="complete",
                from_agent=gov.agent_id, from_role=ROLE_GOVERNANCE, to_role=None,
                task_ref=task_ref, payload={"closed": True},
                correlation_id=m.id,
            ))
            steps.append("complete")

    bus.subscribe(on_research_request, type="research_request")
    bus.subscribe(on_research_result, type="research_result")
    bus.subscribe(on_delivery_request, type="delivery_request")
    bus.subscribe(on_delivery_registered, type="delivery_registered")
    bus.subscribe(on_assign, type="assign")
    bus.subscribe(on_claim_ack, type="claim_ack")
    bus.subscribe(on_handoff, type="handoff")
    bus.subscribe(on_verify, type="verify_result")

    # kick: governance dispatch research
    bus.publish(RoleMessage(
        id=uuid.uuid4().hex, type="research_request",
        from_agent=gov.agent_id, from_role=ROLE_GOVERNANCE, to_role=ROLE_RESEARCH,
        task_ref=task_ref, payload={"query": "research needed"},
    ))

    completed = "complete" in steps and state.get("verify") is True
    return {
        "task_ref": task_ref,
        "completed": completed,
        "steps": steps,
        "replay": bus.replay(),
        "roles": [ROLE_GOVERNANCE, ROLE_RESEARCH, ROLE_DELIVERY, ROLE_ENGINEERING, ROLE_AUDIT],
        "error": None if completed else "handshake_incomplete",
        "bus": bus,
    }


def measure_five_role_batch(
    *, n_tasks: int = 15, inject_fail_every: int = 0
) -> dict[str, Any]:
    """C1 5 角色协作批次测量 (G-DEL.2b 5-role 口径, ADR-0235 扩容验证).

    5 角色 (engineering/governance/audit/research/delivery) dispatch 流批次.
    Note: ``meets_gate`` from ``stamp_non_physical_goal`` = process-local 协议成功,
    非 official G-DEL.2b 物理达标 (5 角色正式实装须人类拍板).
    """
    from caliber import stamp_non_physical_goal

    ok = 0
    trails: list[dict[str, Any]] = []
    for i in range(n_tasks):
        fail = inject_fail_every > 0 and (i % inject_fail_every == 0)
        r = run_five_role_handshake(fail_verify=fail)
        if r["completed"]:
            ok += 1
        trails.append(
            {"task_ref": r["task_ref"], "completed": r["completed"], "steps": r["steps"]}
        )
    rate = ok / n_tasks if n_tasks else 0.0
    stamped = stamp_non_physical_goal(
        {
            "n_tasks": n_tasks,
            "completed": ok,
            "completion_rate": rate,
            "completion_rate_pct": round(rate * 100, 4),
            "gate": "G-DEL.2b-5role",
            "kpi": "5-role collab completion > 95%",
            "env": "process-local RoleProtocolBus (C1 expansion, ADR-0235)",
            "roles": list(ALL_ROLES),
            "trails_sample": trails[:5],
            "trails_all_count": len(trails),
            "official_announce": False,
        },
        ok=rate > 0.95,
    )
    # Explicit: process-local gate must never flip physical
    stamped["meets_physical_gate"] = False
    return stamped
