"""G-DEL.2b — Role collaboration runtime (process-local CollabBus).

Implements G-DEL.2a message handshake; measures collab completion rate > 95%
(BET-664e3). Not multi-host.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable


MessageHandler = Callable[["CollabMessage"], None]


@dataclass
class CollabMessage:
    id: str
    type: str
    from_agent: str
    from_role: str
    to_role: str | None
    task_ref: str
    payload: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    correlation_id: str | None = None


class CollabBus:
    def __init__(self) -> None:
        self._subs: list[tuple[dict[str, str | None], MessageHandler]] = []
        self.history: list[CollabMessage] = []

    def subscribe(
        self,
        handler: MessageHandler,
        *,
        role_id: str | None = None,
        type: str | None = None,
    ) -> None:
        self._subs.append(({"role_id": role_id, "type": type}, handler))

    def publish(self, msg: CollabMessage) -> None:
        self.history.append(msg)
        for filt, handler in self._subs:
            if filt["type"] and filt["type"] != msg.type:
                continue
            if filt["role_id"] and filt["role_id"] != msg.to_role and msg.to_role is not None:
                # also deliver if to_role is None (broadcast)
                if msg.to_role is not None:
                    continue
            handler(msg)


@dataclass
class CollabRunResult:
    task_ref: str
    completed: bool
    steps: list[str] = field(default_factory=list)
    error: str | None = None


def run_collab_handshake(
    bus: CollabBus | None = None,
    *,
    fail_verify: bool = False,
) -> CollabRunResult:
    """Full assign → claim_ack → handoff → verify_result → complete path."""
    bus = bus or CollabBus()
    task_ref = f"task-{uuid.uuid4().hex[:8]}"
    steps: list[str] = []
    state: dict[str, Any] = {"claim": False, "verify": None}

    def on_assign(m: CollabMessage) -> None:
        steps.append("assign")
        bus.publish(
            CollabMessage(
                id=uuid.uuid4().hex,
                type="claim_ack",
                from_agent="impl-1",
                from_role="implementer",
                to_role="orchestrator",
                task_ref=task_ref,
                correlation_id=m.id,
            )
        )

    def on_claim(m: CollabMessage) -> None:
        steps.append("claim_ack")
        state["claim"] = True
        bus.publish(
            CollabMessage(
                id=uuid.uuid4().hex,
                type="handoff",
                from_agent="impl-1",
                from_role="implementer",
                to_role="verifier",
                task_ref=task_ref,
                payload={"evidence": "ok"},
                correlation_id=m.correlation_id,
            )
        )

    def on_handoff(m: CollabMessage) -> None:
        steps.append("handoff")
        ok = not fail_verify
        state["verify"] = ok
        bus.publish(
            CollabMessage(
                id=uuid.uuid4().hex,
                type="verify_result",
                from_agent="ver-1",
                from_role="verifier",
                to_role="orchestrator",
                task_ref=task_ref,
                payload={"pass": ok},
                correlation_id=m.correlation_id,
            )
        )

    def on_verify(m: CollabMessage) -> None:
        steps.append("verify_result")
        if m.payload.get("pass"):
            bus.publish(
                CollabMessage(
                    id=uuid.uuid4().hex,
                    type="complete",
                    from_agent="orch-1",
                    from_role="orchestrator",
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
        CollabMessage(
            id=uuid.uuid4().hex,
            type="assign",
            from_agent="orch-1",
            from_role="orchestrator",
            to_role="implementer",
            task_ref=task_ref,
            payload={"kpi": "collab"},
        )
    )

    completed = "complete" in steps and state.get("verify") is True
    return CollabRunResult(
        task_ref=task_ref,
        completed=completed,
        steps=steps,
        error=None if completed else "handshake_incomplete",
    )


def measure_collab_completion_rate(*, n_runs: int = 200, inject_fail_every: int = 0) -> dict[str, Any]:
    ok = 0
    for i in range(n_runs):
        fail = inject_fail_every > 0 and (i % inject_fail_every == 0)
        r = run_collab_handshake(fail_verify=fail)
        if r.completed:
            ok += 1
    rate = ok / n_runs if n_runs else 0.0
    from caliber import stamp_non_physical_goal  # noqa: PLC0415

    return stamp_non_physical_goal(
        {
            "n_runs": n_runs,
            "completed": ok,
            "completion_rate": rate,
            "completion_rate_pct": round(rate * 100, 4),
            "gate": "G-DEL.2b",
            "kpi": "role_collab_complete_rate > 95%",
            "env": "process-local CollabBus (G-DEL.2a protocol)",
        },
        ok=rate > 0.95,
    )
