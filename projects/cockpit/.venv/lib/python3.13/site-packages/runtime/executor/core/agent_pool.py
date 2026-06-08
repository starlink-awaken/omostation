"""Agent Pool — Agent 注册表与能力路由。

提供 Agent 定义管理及按能力检索的反向索引功能。
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import dataclass, field


@dataclass
class AgentDef:
    """Agent 定义 — 描述一个可用 Agent 的元数据。

    Attributes:
        name: Agent 名称。
        role: Agent 角色（如 assistant, worker, planner）。
        capabilities: 能力标签列表，用于按能力检索。
        model: 绑定的模型名称。
        status: 当前状态（idle, busy, offline, error）。
        id: 唯一标识符，自动生成。
    """

    name: str
    role: str = "assistant"
    capabilities: list[str] = field(default_factory=list)
    model: str = "deepseek-v4-flash"
    status: str = "idle"
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])


class AgentPool:
    """Agent 注册池。

    维护 Agent 定义的全量注册表及能力到 Agent 的反向索引，
    支持 O(1) 按 ID 查找和 O(k) 按能力检索（k 为匹配 Agent 数）。

    Usage::

        pool = AgentPool()
        agent = AgentDef(name="search-bot", capabilities=["web_search", "rag"])
        aid = pool.add_agent(agent)
        matches = pool.list_by_capability("web_search")
    """

    def __init__(self) -> None:
        self._agents: dict[str, AgentDef] = {}
        self._capability_index: dict[str, set[str]] = defaultdict(set)

    def add_agent(self, agent_def: AgentDef) -> str:
        """注册一个 Agent。

        Args:
            agent_def: Agent 定义对象。若 id 为空则自动生成。

        Returns:
            注册后的 agent_id。
        """
        if not agent_def.id:
            agent_def.id = uuid.uuid4().hex[:12]
        self._agents[agent_def.id] = agent_def
        for cap in agent_def.capabilities:
            self._capability_index[cap].add(agent_def.id)
        return agent_def.id

    def remove_agent(self, agent_id: str) -> bool:
        """移除一个 Agent。

        Args:
            agent_id: 要移除的 Agent ID。

        Returns:
            True 若成功移除，False 若 Agent 不存在。
        """
        agent = self._agents.pop(agent_id, None)
        if agent is None:
            return False
        for cap in agent.capabilities:
            cap_set = self._capability_index.get(cap)
            if cap_set:
                cap_set.discard(agent_id)
                if not cap_set:
                    del self._capability_index[cap]
        return True

    def get_agent(self, agent_id: str) -> AgentDef | None:
        """按 ID 获取 Agent 定义。

        Args:
            agent_id: Agent ID。

        Returns:
            AgentDef 若存在，否则 None。
        """
        return self._agents.get(agent_id)

    def list_by_capability(self, capability: str) -> list[AgentDef]:
        """按能力标签列出所有匹配的 Agent。

        Args:
            capability: 能力标签。

        Returns:
            匹配的 AgentDef 列表。若无匹配则返回空列表。
        """
        ids = self._capability_index.get(capability, set())
        return [self._agents[aid] for aid in ids if aid in self._agents]

    def list_all(self) -> list[AgentDef]:
        """列出所有已注册的 Agent。"""
        return list(self._agents.values())

    def update_status(self, agent_id: str, status: str) -> bool:
        """更新 Agent 状态。

        Args:
            agent_id: Agent ID。
            status: 新状态值（如 idle, busy, offline）。

        Returns:
            True 若成功更新，False 若 Agent 不存在。
        """
        agent = self._agents.get(agent_id)
        if agent is None:
            return False
        agent.status = status
        return True

    def __len__(self) -> int:
        return len(self._agents)

    def __contains__(self, agent_id: str) -> bool:
        return agent_id in self._agents
