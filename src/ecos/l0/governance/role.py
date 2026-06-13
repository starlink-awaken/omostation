"""L0 角色原语 — 为多角色Agent构建基础"""

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
