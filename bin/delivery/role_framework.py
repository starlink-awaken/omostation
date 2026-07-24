"""STRAT-P81 Batch1 B1 — Role framework (3 first-ship roles + protocol).

Maps engineering / governance / audit onto capability sets and collab message
boundaries (G-DEL.2a contract). Process-local only.
"""
from __future__ import annotations

import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

# First-ship roles (workorder B1 suggestion)
ROLE_ENGINEERING = "engineering"
ROLE_GOVERNANCE = "governance"
ROLE_AUDIT = "audit"

FIRST_SHIP_ROLES = (ROLE_ENGINEERING, ROLE_GOVERNANCE, ROLE_AUDIT)

# Map to legacy G-DEL.2a role ids used by CollabBus handshake
LEGACY_ROLE_MAP = {
    ROLE_ENGINEERING: "implementer",
    ROLE_GOVERNANCE: "orchestrator",
    ROLE_AUDIT: "verifier",
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
        capabilities=("assign", "claim-path", "write-adr", "closeout"),
        can_send=("assign", "complete", "progress", "block"),
        can_recv=("claim_ack", "handoff", "verify_result", "block", "progress"),
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


def run_three_role_handshake(
    bus: RoleProtocolBus | None = None,
    *,
    fail_verify: bool = False,
) -> dict[str, Any]:
    """Full assign→claim→handoff→verify→complete across 3 first-ship roles."""
    bus = bus or RoleProtocolBus()
    reg = bus.registry
    eng = reg.register(ROLE_ENGINEERING, agent_id="eng-1")
    gov = reg.register(ROLE_GOVERNANCE, agent_id="gov-1")
    aud = reg.register(ROLE_AUDIT, agent_id="aud-1")
    task_ref = f"batch1-task-{uuid.uuid4().hex[:8]}"
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
                payload={"evidence": "ok"},
                correlation_id=m.correlation_id or m.id,
            )
        )

    def on_handoff(m: RoleMessage) -> None:
        steps.append("handoff")
        ok = not fail_verify
        state["verify"] = ok
        bus.publish(
            RoleMessage(
                id=uuid.uuid4().hex,
                type="verify_result",
                from_agent=aud.agent_id,
                from_role=ROLE_AUDIT,
                to_role=ROLE_GOVERNANCE,
                task_ref=task_ref,
                payload={"pass": ok},
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
            payload={"kpi": "batch1-collab"},
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
    }


def measure_three_role_batch(
    *, n_tasks: int = 30, inject_fail_every: int = 0
) -> dict[str, Any]:
    """G-DEL.2b-style batch measure for 3 first-ship roles."""
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
    return stamp_non_physical_goal(
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
        },
        ok=rate > 0.95,
    )


def run_backlog_collab(
    *,
    task_id: str,
    task_path: str,
    title: str = "",
    work_summary: str = "",
    fail_verify: bool = False,
) -> dict[str, Any]:
    """Run 3-role collab bound to a **real** backlog task id/path (Batch1 B2).

    Unlike synthetic ``run_three_role_handshake`` (auto UUID task_ref), this uses
    the backlog ``task_id`` as ``task_ref`` and records path + handoff evidence
    in the protocol payload for audit trails.
    """
    if not task_id or not task_path:
        raise ValueError("task_id and task_path required for real backlog collab")
    bus = RoleProtocolBus()
    reg = bus.registry
    eng = reg.register(ROLE_ENGINEERING, agent_id=f"eng-{task_id[:12]}")
    gov = reg.register(ROLE_GOVERNANCE, agent_id=f"gov-{task_id[:12]}")
    aud = reg.register(ROLE_AUDIT, agent_id=f"aud-{task_id[:12]}")
    task_ref = task_id
    steps: list[str] = []
    state: dict[str, Any] = {}
    handoff_evidence = {
        "task_id": task_id,
        "task_path": task_path,
        "title": title or task_id,
        "work_summary": work_summary
        or f"3-role collab review on backlog item {task_id}",
        "artifacts": [task_path],
    }

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
                payload={"claimed_path": task_path},
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
                payload={"evidence": handoff_evidence},
                correlation_id=m.correlation_id or m.id,
            )
        )

    def on_handoff(m: RoleMessage) -> None:
        steps.append("handoff")
        ok = not fail_verify
        # audit verifies real path exists when possible
        from pathlib import Path as _P

        path_ok = _P(task_path).is_file() or _P(task_path).exists()
        state["verify"] = ok and path_ok
        bus.publish(
            RoleMessage(
                id=uuid.uuid4().hex,
                type="verify_result",
                from_agent=aud.agent_id,
                from_role=ROLE_AUDIT,
                to_role=ROLE_GOVERNANCE,
                task_ref=task_ref,
                payload={
                    "pass": state["verify"],
                    "task_path": task_path,
                    "path_exists": path_ok,
                    "evidence_keys": list(handoff_evidence.keys()),
                },
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
                    payload={"task_path": task_path, "closed": True},
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
            payload={
                "kpi": "real-backlog-collab",
                "task_id": task_id,
                "task_path": task_path,
                "title": title,
            },
        )
    )

    completed = "complete" in steps and state.get("verify") is True
    return {
        "task_ref": task_ref,
        "task_id": task_id,
        "task_path": task_path,
        "title": title,
        "completed": completed,
        "steps": steps,
        "replay": bus.replay(),
        "roles": [eng.role_id, gov.role_id, aud.role_id],
        "handoff_evidence": handoff_evidence,
        "error": None if completed else "handshake_incomplete_or_path_missing",
    }
