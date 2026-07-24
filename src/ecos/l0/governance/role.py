"""L0 角色原语 — 为多角色Agent构建基础

支持多角色Agent的核心组件：
- RoleManager: 角色管理器 (定义/分配/切换/列表)
- RoleCollaboration: 角色协作协议
- RoleSwitcher: 动态切换机制
- RoleEvaluator: 角色评估
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from ecos.common.logger import get_logger

logger = get_logger("role")


class RoleType(Enum):
    """角色类型

    M1 定义: Agent 角色分类
    """

    WORKER = "worker"  # 工作角色
    COORDINATOR = "coordinator"  # 协调角色
    SPECIALIST = "specialist"  # 专家角色
    MANAGER = "manager"  # 管理角色


class RoleStatus(Enum):
    """角色状态"""

    ACTIVE = "active"
    INACTIVE = "inactive"
    SWITCHING = "switching"


class CollaborationMode(Enum):
    """协作模式"""

    SEQUENTIAL = "sequential"  # 顺序执行
    PARALLEL = "parallel"  # 并行执行
    PIPELINE = "pipeline"  # 流水线
    VOTING = "voting"  # 投票决策


@dataclass
class RoleDefinition:
    """角色定义

    L0 原语: Agent 角色的基本定义
    """

    role_id: str
    role_type: RoleType
    capabilities: list[str]
    constraints: dict[str, Any]
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "role_id": self.role_id,
            "role_type": self.role_type.value,
            "capabilities": self.capabilities,
            "constraints": self.constraints,
            "metadata": self.metadata,
        }


@dataclass
class AgentRole:
    """Agent 角色映射"""

    agent_id: str
    role_id: str
    status: RoleStatus
    assigned_at: Optional[datetime] = None

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "agent_id": self.agent_id,
            "role_id": self.role_id,
            "status": self.status.value,
            "assigned_at": self.assigned_at.isoformat() if self.assigned_at else None,
        }


@dataclass
class CollaborationTask:
    """协作任务"""

    task_id: str
    name: str
    required_roles: list[str]
    mode: CollaborationMode = CollaborationMode.SEQUENTIAL
    status: str = "pending"
    results: dict[str, Any] = field(default_factory=dict)


@dataclass
class RoleEvaluation:
    """角色评估"""

    agent_id: str
    role_id: str
    score: float  # 0-100
    metrics: dict[str, float] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class RolePrimitive(ABC):
    """角色原语基类

    L0 原语: 所有角色操作必须继承此基类
    """

    @abstractmethod
    def define_role(self, definition: RoleDefinition) -> bool:
        """定义角色"""
        pass

    @abstractmethod
    def assign_role(self, agent_id: str, role_id: str) -> bool:
        """分配角色"""
        pass

    @abstractmethod
    def switch_role(self, agent_id: str, new_role_id: str) -> bool:
        """切换角色"""
        pass

    @abstractmethod
    def get_role(self, agent_id: str) -> Optional[RoleDefinition]:
        """获取角色"""
        pass

    @abstractmethod
    def list_roles(self) -> list[RoleDefinition]:
        """列出所有角色"""
        pass


class RoleManager(RolePrimitive):
    """角色管理器实现"""

    def __init__(self, persistence=None):
        self.roles: dict[str, RoleDefinition] = {}
        self._persistence = persistence
        self.agent_roles: dict[str, AgentRole] = {}

    def define_role(self, definition: RoleDefinition) -> bool:
        """定义角色"""
        try:
            if definition.role_id in self.roles:
                logger.warning("角色已存在: %s", definition.role_id)
                return False
            self.roles[definition.role_id] = definition
            logger.info(
                "定义角色: %s, type=%s", definition.role_id, definition.role_type.value
            )
            return True
        except Exception as e:  # defensive fallback
            logger.error("定义角色失败: %s - %s", definition.role_id, str(e))
            return False

    def assign_role(self, agent_id: str, role_id: str) -> bool:
        """分配角色"""
        try:
            if role_id not in self.roles:
                logger.warning("角色不存在: %s", role_id)
                return False

            self.agent_roles[agent_id] = AgentRole(
                agent_id=agent_id,
                role_id=role_id,
                status=RoleStatus.ACTIVE,
                assigned_at=datetime.now(timezone.utc),
            )
            logger.info("分配角色: agent=%s, role=%s", agent_id, role_id)
            return True
        except Exception as e:  # defensive fallback
            logger.error(
                "分配角色失败: agent=%s, role=%s - %s", agent_id, role_id, str(e)
            )
            return False

    def switch_role(self, agent_id: str, new_role_id: str) -> bool:
        """切换角色"""
        try:
            if agent_id not in self.agent_roles:
                logger.warning("Agent 不存在: %s", agent_id)
                return False
            if new_role_id not in self.roles:
                logger.warning("角色不存在: %s", new_role_id)
                return False

            old_role = self.agent_roles[agent_id].role_id
            self.agent_roles[agent_id].role_id = new_role_id
            self.agent_roles[agent_id].status = RoleStatus.ACTIVE
            logger.info("切换角色: agent=%s, %s -> %s", agent_id, old_role, new_role_id)
            return True
        except Exception as e:  # defensive fallback
            logger.error("切换角色失败: agent=%s - %s", agent_id, str(e))
            return False

    def get_role(self, agent_id: str) -> Optional[RoleDefinition]:
        """获取角色"""
        if agent_id not in self.agent_roles:
            return None

        role_id = self.agent_roles[agent_id].role_id
        return self.roles.get(role_id)

    def list_roles(self) -> list[RoleDefinition]:
        """列出所有角色"""
        return list(self.roles.values())

    def get_agents_by_role(self, role_id: str) -> list[AgentRole]:
        """获取指定角色的所有 Agent"""
        return [a for a in self.agent_roles.values() if a.role_id == role_id]

    def _load_state(self):
        """从持久化加载状态"""
        if not self._persistence:
            return
        try:
            saved = self._persistence.load("role_manager")
            if saved:
                logger.info("从持久化加载状态: role_manager")
        except Exception as e:  # defensive fallback
            logger.error("加载状态失败: %s", str(e))

    def _save_state(self):
        """保存状态到持久化"""
        if not self._persistence:
            return
        try:
            self._persistence.save("role_manager", {"placeholder": True})
            logger.debug("保存状态: role_manager")
        except Exception as e:  # defensive fallback
            logger.error("保存状态失败: %s", str(e))


class RoleCollaboration:
    """角色协作协议

    管理多角色 Agent 之间的协作
    """

    def __init__(self, role_manager: RoleManager):
        self.role_manager = role_manager
        self.tasks: dict[str, CollaborationTask] = {}

    def create_task(
        self,
        task_id: str,
        name: str,
        required_roles: list[str],
        mode: CollaborationMode = CollaborationMode.SEQUENTIAL,
    ) -> CollaborationTask:
        """创建协作任务"""
        task = CollaborationTask(
            task_id=task_id,
            name=name,
            required_roles=required_roles,
            mode=mode,
        )
        self.tasks[task_id] = task
        return task

    def assign_roles_to_task(
        self, task_id: str, agent_assignments: dict[str, str]
    ) -> bool:
        """为任务分配角色"""
        if task_id not in self.tasks:
            return False

        task = self.tasks[task_id]

        # 检查是否所有必需角色都已分配
        for role in task.required_roles:
            if role not in agent_assignments:
                return False

        # 分配角色
        for role_id, agent_id in agent_assignments.items():
            self.role_manager.assign_role(agent_id, role_id)
            task.results[role_id] = {"agent_id": agent_id, "status": "assigned"}

        task.status = "assigned"
        return True

    def start_task(self, task_id: str) -> bool:
        """开始任务"""
        if task_id not in self.tasks:
            return False

        task = self.tasks[task_id]
        if task.status != "assigned":
            return False

        task.status = "running"
        return True

    def complete_task(
        self, task_id: str, results: dict[str, Any] | None = None
    ) -> bool:
        """完成任务"""
        if task_id not in self.tasks:
            return False

        task = self.tasks[task_id]
        if task.status != "running":
            return False

        task.status = "completed"
        if results:
            task.results.update(results)
        return True

    def get_task(self, task_id: str) -> Optional[CollaborationTask]:
        """获取任务"""
        return self.tasks.get(task_id)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "tasks": {
                tid: {
                    "name": t.name,
                    "required_roles": t.required_roles,
                    "mode": t.mode.value,
                    "status": t.status,
                    "results": t.results,
                }
                for tid, t in self.tasks.items()
            }
        }


class RoleEvaluator:
    """角色评估器

    评估 Agent 角色表现
    """

    def __init__(self, persistence=None):
        self.evaluations: list[RoleEvaluation] = []

    def evaluate(
        self,
        agent_id: str,
        role_id: str,
        score: float,
        metrics: dict[str, float] | None = None,
    ) -> RoleEvaluation:
        """评估角色表现"""
        evaluation = RoleEvaluation(
            agent_id=agent_id,
            role_id=role_id,
            score=score,
            metrics=metrics or {},
        )
        self.evaluations.append(evaluation)
        return evaluation

    def get_evaluation(self, agent_id: str) -> Optional[RoleEvaluation]:
        """获取 Agent 最新评估"""
        agent_evals = [e for e in self.evaluations if e.agent_id == agent_id]
        if agent_evals:
            return max(agent_evals, key=lambda e: e.timestamp)
        return None

    def get_average_score(self, role_id: str | None = None) -> float:
        """获取平均分"""
        if role_id:
            evals = [e for e in self.evaluations if e.role_id == role_id]
        else:
            evals = self.evaluations

        if not evals:
            return 0.0

        return sum(e.score for e in evals) / len(evals)

    def get_top_agents(self, role_id: str, limit: int = 5) -> list[RoleEvaluation]:
        """获取表现最好的 Agent"""
        role_evals = [e for e in self.evaluations if e.role_id == role_id]
        role_evals.sort(key=lambda e: e.score, reverse=True)
        return role_evals[:limit]

    def get_improvement_trend(self, agent_id: str, role_id: str) -> Optional[str]:
        """评估 Agent 改进趋势"""
        agent_evals = sorted(
            [
                e
                for e in self.evaluations
                if e.agent_id == agent_id and e.role_id == role_id
            ],
            key=lambda e: e.timestamp,
        )
        if len(agent_evals) < 2:
            return None

        recent_avg = sum(e.score for e in agent_evals[-3:]) / min(len(agent_evals), 3)
        older_avg = sum(e.score for e in agent_evals[:-3]) / max(
            len(agent_evals) - 3, 1
        )

        if recent_avg > older_avg + 5:
            return "improving"
        elif recent_avg < older_avg - 5:
            return "declining"
        return "stable"

    def get_role_ranking(self, role_id: str) -> list[tuple[str, float]]:
        """获取角色的 Agent 排名"""
        agent_scores: dict[str, list[float]] = defaultdict(list)
        for e in self.evaluations:
            if e.role_id == role_id:
                agent_scores[e.agent_id].append(e.score)

        ranking = [
            (agent_id, sum(scores) / len(scores))
            for agent_id, scores in agent_scores.items()
        ]
        ranking.sort(key=lambda x: x[1], reverse=True)
        return ranking

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "evaluations": [
                {
                    "agent_id": e.agent_id,
                    "role_id": e.role_id,
                    "score": e.score,
                    "metrics": e.metrics,
                    "timestamp": e.timestamp.isoformat(),
                }
                for e in self.evaluations
            ]
        }


class RoleSwitcher:
    """角色动态切换器 — 支持冷却期、前置角色验证、切换历史"""

    def __init__(self, role_manager: RoleManager, cooldown_seconds: int = 5):
        self.role_manager = role_manager
        self.cooldown_seconds = cooldown_seconds
        self._last_switch: dict[str, datetime] = {}
        self._switch_history: list[dict[str, Any]] = []
        self._role_prerequisites: dict[str, list[str]] = {}
        self._role_conflicts: dict[str, set[str]] = {}

    def set_prerequisites(self, role_id: str, prerequisites: list[str]) -> None:
        """设置角色前置条件 — Agent 必须先拥有前置角色才能切换"""
        self._role_prerequisites[role_id] = prerequisites

    def set_conflicts(self, role_id: str, conflicting_roles: list[str]) -> None:
        """设置角色冲突 — 不能同时拥有冲突的角色"""
        self._role_conflicts[role_id] = set(conflicting_roles)

    def can_switch(self, agent_id: str, new_role_id: str) -> tuple[bool, str]:
        """检查是否可以切换"""
        now = datetime.now(timezone.utc)

        last = self._last_switch.get(agent_id)
        if last:
            elapsed = (now - last).total_seconds()
            if elapsed < self.cooldown_seconds:
                remaining = self.cooldown_seconds - elapsed
                return False, f"冷却期未结束，还需 {remaining:.1f} 秒"

        if new_role_id not in self.role_manager.roles:
            return False, f"角色 {new_role_id} 不存在"

        prereqs = self._role_prerequisites.get(new_role_id, [])
        if prereqs:
            current = self.role_manager.agent_roles.get(agent_id)
            if current and current.role_id not in prereqs:
                return False, f"需要前置角色: {', '.join(prereqs)}"

        current = self.role_manager.agent_roles.get(agent_id)
        if current:
            conflicts = self._role_conflicts.get(new_role_id, set())
            if current.role_id in conflicts:
                return False, f"与当前角色 {current.role_id} 冲突"

        return True, "可以切换"

    def switch(self, agent_id: str, new_role_id: str) -> tuple[bool, str]:
        """执行角色切换"""
        can, reason = self.can_switch(agent_id, new_role_id)
        if not can:
            return False, reason

        old_role_id = ""
        if agent_id in self.role_manager.agent_roles:
            old_role_id = self.role_manager.agent_roles[agent_id].role_id

        success = self.role_manager.switch_role(agent_id, new_role_id)
        if success:
            self._last_switch[agent_id] = datetime.now(timezone.utc)
            self._switch_history.append(
                {
                    "agent_id": agent_id,
                    "old_role": old_role_id,
                    "new_role": new_role_id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )
            return True, f"切换成功: {old_role_id} → {new_role_id}"

        return False, "切换失败"

    def get_switch_history(
        self, agent_id: str | None = None, limit: int = 50
    ) -> list[dict[str, Any]]:
        """获取切换历史"""
        if agent_id:
            history = [h for h in self._switch_history if h["agent_id"] == agent_id]
        else:
            history = self._switch_history
        return history[-limit:]

    def get_role_distribution(self) -> dict[str, list[str]]:
        """获取当前角色分布"""
        distribution: dict[str, list[str]] = defaultdict(list)
        for agent_id, agent_role in self.role_manager.agent_roles.items():
            distribution[agent_role.role_id].append(agent_id)
        return dict(distribution)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "cooldown_seconds": self.cooldown_seconds,
            "prerequisites": self._role_prerequisites,
            "conflicts": {k: list(v) for k, v in self._role_conflicts.items()},
            "switch_count": len(self._switch_history),
            "distribution": self.get_role_distribution(),
        }
