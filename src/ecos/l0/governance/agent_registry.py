"""L0 分布式原语 — Agent 注册中心

实现多机协作的核心组件：
- AgentRegistry: Agent 注册中心
- AgentInfo: Agent 信息
- AgentStatus: Agent 状态枚举
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from ecos.common.logger import get_logger

logger = get_logger("agent_registry")


class AgentStatus(Enum):
    """Agent 状态"""

    IDLE = "idle"
    BUSY = "busy"
    OFFLINE = "offline"
    ERROR = "error"


@dataclass
class AgentInfo:
    """Agent 信息"""

    agent_id: str
    name: str
    capabilities: list[str]
    status: AgentStatus = AgentStatus.IDLE
    node_id: str = ""
    last_heartbeat: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "capabilities": self.capabilities,
            "status": self.status.value,
            "node_id": self.node_id,
            "last_heartbeat": self.last_heartbeat.isoformat(),
            "metadata": self.metadata,
        }


class AgentRegistry:
    """Agent 注册中心

    管理分布式系统中的 Agent 注册、发现和健康检查
    """

    def __init__(self, persistence=None):
        self.agents: dict[str, AgentInfo] = {}
        self._persistence = persistence
        self.heartbeat_interval: int = 30  # 秒

    def register(
        self,
        agent_id: str,
        name: str,
        capabilities: list[str],
        node_id: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> AgentInfo:
        """注册 Agent"""
        try:
            if agent_id in self.agents:
                logger.warning("Agent 已存在: %s", agent_id)
                return self.agents[agent_id]

            agent = AgentInfo(
                agent_id=agent_id,
                name=name,
                capabilities=capabilities,
                node_id=node_id,
                metadata=metadata or {},
            )
            self.agents[agent_id] = agent
            logger.info(
                "注册 Agent: %s, name=%s, capabilities=%s", agent_id, name, capabilities
            )
            return agent
        except Exception as e:  # defensive fallback
            logger.error("注册 Agent 失败: %s - %s", agent_id, str(e))
            raise

    def unregister(self, agent_id: str) -> bool:
        """注销 Agent"""
        try:
            if agent_id in self.agents:
                del self.agents[agent_id]
                logger.info("注销 Agent: %s", agent_id)
                return True
            return False
        except Exception as e:  # defensive fallback
            logger.error("注销 Agent 失败: %s - %s", agent_id, str(e))
            return False

    def get_agent(self, agent_id: str) -> AgentInfo | None:
        """获取 Agent 信息"""
        return self.agents.get(agent_id)

    def get_all_agents(self) -> list[AgentInfo]:
        """获取所有 Agent"""
        return list(self.agents.values())

    def get_agents_by_capability(self, capability: str) -> list[AgentInfo]:
        """按能力查找 Agent"""
        return [a for a in self.agents.values() if capability in a.capabilities]

    def get_agents_by_status(self, status: AgentStatus) -> list[AgentInfo]:
        """按状态查找 Agent"""
        return [a for a in self.agents.values() if a.status == status]

    def get_idle_agents(self) -> list[AgentInfo]:
        """获取空闲 Agent"""
        return self.get_agents_by_status(AgentStatus.IDLE)

    def update_status(self, agent_id: str, status: AgentStatus) -> bool:
        """更新 Agent 状态"""
        if agent_id in self.agents:
            self.agents[agent_id].status = status
            self.agents[agent_id].last_heartbeat = datetime.now(timezone.utc)
            return True
        return False

    def update_heartbeat(self, agent_id: str) -> bool:
        """更新心跳"""
        if agent_id in self.agents:
            self.agents[agent_id].last_heartbeat = datetime.now(timezone.utc)
            return True
        return False

    def discover_agents(self, capability: str) -> list[AgentInfo]:
        """发现具有特定能力的 Agent"""
        return [
            a
            for a in self.agents.values()
            if capability in a.capabilities and a.status == AgentStatus.IDLE
        ]

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "agents": {aid: a.to_dict() for aid, a in self.agents.items()},
            "heartbeat_interval": self.heartbeat_interval,
        }

    def _load_state(self):
        """从持久化加载状态"""
        if not self._persistence:
            return
        try:
            saved = self._persistence.load("agent_registry")
            if saved:
                logger.info("从持久化加载状态: agent_registry")
        except Exception as e:  # defensive fallback
            logger.error("加载状态失败: %s", str(e))

    def _save_state(self):
        """保存状态到持久化"""
        if not self._persistence:
            return
        try:
            self._persistence.save("agent_registry", {"placeholder": True})
            logger.debug("保存状态: agent_registry")
        except Exception as e:  # defensive fallback
            logger.error("保存状态失败: %s", str(e))
