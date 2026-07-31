"""Agent Registry — JSON file persistence with in-memory cache."""

from __future__ import annotations

import json
import logging
import threading
from datetime import UTC, datetime
from pathlib import Path

from .models import AgentInfo, AgentStatus, NodeInfo

logger = logging.getLogger(__name__)


class RegistryStore:
    def __init__(self, persist_path: str | Path | None = None) -> None:
        self._lock = threading.Lock()
        self._agents: dict[str, AgentInfo] = {}
        self._nodes: dict[str, NodeInfo] = {}
        self._persist_path = Path(persist_path) if persist_path else None
        if self._persist_path and self._persist_path.exists():
            self._load()

    def register_agent(self, agent: AgentInfo) -> AgentInfo:
        with self._lock:
            self._agents[agent.agent_id] = agent
            self._save()
            return agent

    def get_agent(self, agent_id: str) -> AgentInfo | None:
        return self._agents.get(agent_id)

    def update_agent(self, agent_id: str, **kwargs) -> AgentInfo | None:
        with self._lock:
            agent = self._agents.get(agent_id)
            if agent is None:
                return None
            for key, value in kwargs.items():
                if hasattr(agent, key):
                    setattr(agent, key, value)
            agent.last_heartbeat = datetime.now(UTC)
            self._save()
            return agent

    def heartbeat(self, agent_id: str) -> bool:
        with self._lock:
            agent = self._agents.get(agent_id)
            if agent is None:
                return False
            agent.last_heartbeat = datetime.now(UTC)
            self._save()
            return True

    def set_agent_status(self, agent_id: str, status: AgentStatus) -> bool:
        """Change liveness state without refreshing the remote heartbeat."""
        with self._lock:
            agent = self._agents.get(agent_id)
            if agent is None:
                return False
            agent.status = status
            self._save()
            return True

    def mark_node_agents_offline(self, node_id: str) -> list[str]:
        """Fail closed for agents owned by an unreachable peer node."""
        with self._lock:
            marked: list[str] = []
            for agent in self._agents.values():
                if agent.node_id == node_id and agent.status != AgentStatus.REMOTE_OFFLINE:
                    agent.status = AgentStatus.REMOTE_OFFLINE
                    marked.append(agent.agent_id)
            if marked:
                self._save()
            return marked

    def remove_agent(self, agent_id: str) -> bool:
        with self._lock:
            removed = self._agents.pop(agent_id, None)
            if removed:
                self._save()
            return removed is not None

    def find_agents(
        self,
        capabilities: list[str] | None = None,
        status: AgentStatus | None = None,
        node_id: str | None = None,
    ) -> list[AgentInfo]:
        result = list(self._agents.values())
        if capabilities:
            result = [a for a in result if a.can_handle(capabilities)]
        if status is not None:
            result = [a for a in result if a.status == status]
        if node_id is not None:
            result = [a for a in result if a.node_id == node_id]
        return result

    def list_agents(self) -> list[AgentInfo]:
        return list(self._agents.values())

    def register_node(self, node: NodeInfo) -> NodeInfo:
        with self._lock:
            self._nodes[node.node_id] = node
            self._save()
            return node

    def get_node(self, node_id: str) -> NodeInfo | None:
        return self._nodes.get(node_id)

    def heartbeat_node(self, node_id: str) -> bool:
        with self._lock:
            node = self._nodes.get(node_id)
            if node is None:
                return False
            node.last_heartbeat = datetime.now(UTC)
            self._save()
            return True

    def remove_node(self, node_id: str) -> bool:
        with self._lock:
            removed = self._nodes.pop(node_id, None)
            if removed:
                self._save()
            return removed is not None

    def list_nodes(self) -> list[NodeInfo]:
        return list(self._nodes.values())

    def _save(self) -> None:
        if not self._persist_path:
            return
        data = {
            "agents": {k: v.to_dict() for k, v in self._agents.items()},
            "nodes": {k: v.to_dict() for k, v in self._nodes.items()},
            "saved_at": datetime.now(UTC).isoformat(),
        }
        self._persist_path.parent.mkdir(parents=True, exist_ok=True)
        self._persist_path.write_text(json.dumps(data, indent=2, ensure_ascii=False))

    def _load(self) -> None:
        if not self._persist_path or not self._persist_path.exists():
            return
        try:
            data = json.loads(self._persist_path.read_text())
            for k, v in data.get("agents", {}).items():
                self._agents[k] = AgentInfo.from_dict(v)
            for k, v in data.get("nodes", {}).items():
                self._nodes[k] = NodeInfo.from_dict(v)
            logger.info("Loaded %d agents, %d nodes from %s", len(self._agents), len(self._nodes), self._persist_path)
        except Exception:
            logger.exception("Failed to load registry from %s", self._persist_path)


__all__ = ["RegistryStore"]
