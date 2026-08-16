"""Agent Sandbox — untrusted agent isolation (stub). Docker default blocked."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

_log = logging.getLogger(__name__)

SANDBOX_DAYS = 7

# ── Terminal states (agent cannot be promoted further) ──
_TERMINAL = frozenset({"active", "rejected", "blocked"})


class AgentSandbox:
    """Sandbox for untrusted agent isolation.

    Status machine::

        register → pending → start_probation → probation
            ↑          └─────────────────────────┤
            │        probation → finalize(True) → active
            │        probation → finalize(False) → rejected
            │        pending | probation | active | rejected → block → blocked
            │        blocked → register (reset)
            └────────────────────────────────────────────────────┘
    """

    def __init__(self) -> None:
        self.agents: dict[str, dict[str, Any]] = {}

    # ── Internal helpers ──

    def _get(self, agent_id: str) -> dict | None:
        return self.agents.get(agent_id)

    # ── Public API ──

    def register(self, agent_id: str) -> dict:
        e: dict[str, Any] = {
            "agent_id": agent_id,
            "status": "pending",
            "registered_at": datetime.now(UTC).isoformat(),
            "probation_end": None,
            "evaluation": [],
            "docker_approved": False,
        }
        self.agents[agent_id] = e
        return e

    def start_probation(self, agent_id: str) -> dict:
        e = self._get(agent_id)
        if e is None:
            return {"error": "not_registered"}
        if e["status"] in _TERMINAL:
            return {"error": f"cannot_start_probation_on_{e['status']}"}
        e["status"] = "probation"
        e["probation_end"] = (datetime.now(UTC) + timedelta(days=SANDBOX_DAYS)).isoformat()
        return e

    def evaluate(self, agent_id: str, action: str, result: str) -> dict:
        e = self._get(agent_id)
        if e is None:
            return {"error": "not_registered"}
        e["evaluation"].append(
            {
                "action": action,
                "result": result,
                "timestamp": datetime.now(UTC).isoformat(),
            }
        )
        return {"ok": True}

    def report(self, agent_id: str) -> dict:
        e = self._get(agent_id)
        if e is None:
            return {"error": "not_registered"}
        anomalies = [x for x in e["evaluation"] if x.get("result") == "anomaly"]
        return {
            "agent_id": agent_id,
            "status": e["status"],
            "actions": len(e["evaluation"]),
            "anomalies": len(anomalies),
            "safe": len(anomalies) == 0,
        }

    def finalize(self, agent_id: str, approved: bool = False) -> dict:
        """Human review — finalizes probation period."""
        e = self._get(agent_id)
        if e is None:
            return {"error": "not_registered"}
        if e["status"] != "probation":
            return {"error": "not_in_probation"}
        e["status"] = "active" if approved else "rejected"
        e["finalized_at"] = datetime.now(UTC).isoformat()
        return {
            "agent_id": agent_id,
            "status": e["status"],
            "approved": approved,
            "finalized_at": e["finalized_at"],
        }

    def block(self, agent_id: str) -> dict:
        """Manually block an agent (overrides any current status)."""
        e = self._get(agent_id)
        if e is None:
            return {"error": "not_registered"}
        e["status"] = "blocked"
        e["blocked_at"] = datetime.now(UTC).isoformat()
        return {"agent_id": agent_id, "status": "blocked"}

    def approve_docker(self, agent_id: str, approved: bool = False) -> dict:
        """Approve or reject Docker execution for an agent."""
        e = self._get(agent_id)
        if e is None:
            return {"error": "not_registered"}
        if e["status"] in ("rejected", "blocked"):
            return {"approved": False, "message": f"Docker blocked - agent status is {e['status']}"}
        if not approved:
            return {"approved": False, "message": "Docker blocked - requires human approval"}
        e["docker_approved"] = True
        return {"approved": True}

    def can_launch_docker(self, agent_id: str) -> bool:
        """Return True if this agent is allowed to launch Docker containers."""
        e = self._get(agent_id)
        if e is None:
            return False
        return bool(e.get("docker_approved"))
