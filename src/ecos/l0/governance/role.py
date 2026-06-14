"""L0 角色原语 — 为多角色Agent构建基础

支持多角色Agent的核心组件：
- RoleManager: 角色管理器 (定义/分配/切换/列表)
- RoleCollaboration: 角色协作协议
- RoleSwitcher: 动态切换机制
- RoleEvaluator: 角色评估
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


class RoleType(Enum):
    """角色类型
    
    M1 定义: Agent 角色分类
    """
    WORKER = "worker"           # 工作角色
    COORDINATOR = "coordinator"  # 协调角色
    SPECIALIST = "specialist"    # 专家角色
    MANAGER = "manager"         # 管理角色


class RoleStatus(Enum):
    """角色状态"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SWITCHING = "switching"


class CollaborationMode(Enum):
    """协作模式"""
    SEQUENTIAL = "sequential"    # 顺序执行
    PARALLEL = "parallel"        # 并行执行
    PIPELINE = "pipeline"        # 流水线
    VOTING = "voting"            # 投票决策


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
    
    def __init__(self):
        self.roles: dict[str, RoleDefinition] = {}
        self.agent_roles: dict[str, AgentRole] = {}
    
    def define_role(self, definition: RoleDefinition) -> bool:
        """定义角色"""
        self.roles[definition.role_id] = definition
        return True
    
    def assign_role(self, agent_id: str, role_id: str) -> bool:
        """分配角色"""
        if role_id not in self.roles:
            return False
        
        self.agent_roles[agent_id] = AgentRole(
            agent_id=agent_id,
            role_id=role_id,
            status=RoleStatus.ACTIVE,
            assigned_at=datetime.now(timezone.utc),
        )
        return True
    
    def switch_role(self, agent_id: str, new_role_id: str) -> bool:
        """切换角色"""
        if agent_id not in self.agent_roles:
            return False
        if new_role_id not in self.roles:
            return False
        
        self.agent_roles[agent_id].role_id = new_role_id
        self.agent_roles[agent_id].status = RoleStatus.ACTIVE
        return True
    
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


class RoleCollaboration:
    """角色协作协议
    
    管理多角色 Agent 之间的协作
    """
    
    def __init__(self, role_manager: RoleManager):
        self.role_manager = role_manager
        self.tasks: dict[str, CollaborationTask] = {}
    
    def create_task(self, task_id: str, name: str, required_roles: list[str],
                    mode: CollaborationMode = CollaborationMode.SEQUENTIAL) -> CollaborationTask:
        """创建协作任务"""
        task = CollaborationTask(
            task_id=task_id,
            name=name,
            required_roles=required_roles,
            mode=mode,
        )
        self.tasks[task_id] = task
        return task
    
    def assign_roles_to_task(self, task_id: str, agent_assignments: dict[str, str]) -> bool:
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
    
    def complete_task(self, task_id: str, results: dict[str, Any] | None = None) -> bool:
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
    
    def __init__(self):
        self.evaluations: list[RoleEvaluation] = []
    
    def evaluate(self, agent_id: str, role_id: str, score: float,
                 metrics: dict[str, float] | None = None) -> RoleEvaluation:
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
