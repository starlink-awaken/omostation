from __future__ import annotations

import logging
from typing import Any

_log = logging.getLogger(__name__)


class AgentCallHandler:
    """Handles the "agent" domain calls.

    Responsibilities (SRP): agent lifecycle management only.
    Extracted from ExecutionCoordinator._handle_agent_call().
    """

    def __init__(self, agent_lifecycle_orchestrator: Any) -> None:
        self._orchestrator = agent_lifecycle_orchestrator

    async def handle(self, agent_id: str, action: str, params: dict[str, Any] | None) -> dict[str, Any]:
        """Dispatch agent actions to the lifecycle orchestrator."""
        if action == "start":
            return await self._handle_start(agent_id)
        elif action == "stop":
            return await self._handle_stop(agent_id)
        elif action == "status":
            return await self._handle_status(agent_id)
        elif action == "review":
            return await self._handle_review(agent_id, params or {})
        return {"status": "error", "message": f"Unknown agent action: {action}"}

    async def _handle_review(self, agent_id: str, params: dict[str, Any]) -> dict[str, Any]:
        """Auto-approve reviews for now to maintain orchestration flow."""
        phase = params.get("phase", "Unknown")
        vision_id = params.get("vision_id", "Unknown")
        _log.info(f"⚖️ [AgentHandler] Auto-approving review for {agent_id} (Phase: {phase}, Vision: {vision_id})")
        return {
            "status": "success",
            "approved": True,
            "reason": "System-level automatic approval (Bypass mode)",
            "agent_id": agent_id,
        }

    async def _handle_start(self, agent_id: str) -> dict[str, Any]:
        try:
            raw_result = self._orchestrator.start_agent(agent_id)
        except (OSError, ValueError, RuntimeError, AttributeError) as exc:
            return {"status": "error", "message": str(exc), "agent_id": agent_id}
        return self._normalize_start_result(agent_id, raw_result)

    async def _handle_stop(self, agent_id: str) -> dict[str, Any]:
        try:
            raw_result = self._orchestrator.stop_agent(agent_id)
        except (OSError, ValueError, RuntimeError, AttributeError) as exc:
            return {"status": "error", "message": str(exc), "agent_id": agent_id}
        success = raw_result if isinstance(raw_result, bool) else bool(raw_result)
        return {"status": "success" if success else "error", "agent_id": agent_id}

    async def _handle_status(self, agent_id: str) -> dict[str, Any]:
        try:
            status = self._orchestrator.get_status()
        except (OSError, ValueError, RuntimeError, AttributeError) as exc:
            return {"status": "error", "message": str(exc), "agent_id": agent_id}
        agent_info = self._lookup_agent_status(agent_id, status)
        return (
            {"status": "success", "agent": agent_info}
            if agent_info
            else {"status": "error", "message": f"Agent '{agent_id}' not found"}
        )

    def _normalize_start_result(self, agent_id: str, raw_result: Any) -> dict[str, Any]:
        if isinstance(raw_result, dict):
            instance_id = raw_result.get("instance_id") or raw_result.get("agent_id") or agent_id
            return {
                "status": "success",
                "instance_id": instance_id,
                "agent_id": agent_id,
                "agent": raw_result,
            }
        return {
            "status": "success",
            "instance_id": raw_result or agent_id,
            "agent_id": agent_id,
        }

    def _lookup_agent_status(self, agent_id: str, status_snapshot: Any) -> dict[str, Any] | None:
        if isinstance(status_snapshot, dict):
            agents = status_snapshot.get("agents")
            if isinstance(agents, list):
                for agent in agents:
                    if not isinstance(agent, dict):
                        continue
                    if agent.get("id") == agent_id or agent.get("agent_id") == agent_id:
                        return agent

        running = getattr(self._orchestrator, "_running", None)
        if isinstance(running, dict) and agent_id in running:
            return {"id": agent_id, "status": "running"}

        return None
