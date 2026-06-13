"""L0 分布式原语 — 为蜂群式AI超级大脑构建分布式基础"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class SyncStrategy(Enum):
    """同步策略
    
    M1 定义: 分布式状态同步策略
    """
    CRDT = "crdt"           # 无冲突复制数据类型
    EVENTUAL = "eventual"   # 最终一致性
    STRONG = "strong"       # 强一致性


class NodeStatus(Enum):
    """节点状态"""
    ONLINE = "online"
    OFFLINE = "offline"
    SYNCING = "syncing"
    CONFLICT = "conflict"


@dataclass
class StateSnapshot:
    """状态快照
    
    L0 原语: 分布式状态的基本单元
    """
    node_id: str
    version: int
    data: dict[str, Any]
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    checksum: str = ""
    
    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "node_id": self.node_id,
            "version": self.version,
            "data": self.data,
            "timestamp": self.timestamp.isoformat(),
            "checksum": self.checksum,
        }


@dataclass
class SyncResult:
    """同步结果"""
    success: bool
    local_version: int
    remote_version: int
    merged_version: int
    conflicts: list[str] = field(default_factory=list)


class DistributedPrimitive(ABC):
    """分布式原语基类
    
    L0 原语: 所有分布式操作必须继承此基类
    """
    
    @abstractmethod
    def sync(self, snapshot: StateSnapshot) -> SyncResult:
        """同步状态"""
        pass
    
    @abstractmethod
    def merge(self, local: StateSnapshot, remote: StateSnapshot) -> StateSnapshot:
        """合并冲突"""
        pass
    
    @abstractmethod
    def get_version(self) -> int:
        """获取当前版本"""
        pass
    
    @abstractmethod
    def get_node_status(self, node_id: str) -> NodeStatus:
        """获取节点状态"""
        pass


class CRDTSync(DistributedPrimitive):
    """CRDT 同步实现"""
    
    def __init__(self, node_id: str):
        self.node_id = node_id
        self.version = 0
        self.data: dict[str, Any] = {}
        self.nodes: dict[str, NodeStatus] = {}
    
    def sync(self, snapshot: StateSnapshot) -> SyncResult:
        """同步状态"""
        # 简化实现：直接合并
        if snapshot.version > self.version:
            self.data.update(snapshot.data)
            self.version = snapshot.version
            return SyncResult(
                success=True,
                local_version=self.version,
                remote_version=snapshot.version,
                merged_version=self.version,
            )
        return SyncResult(
            success=False,
            local_version=self.version,
            remote_version=snapshot.version,
            merged_version=self.version,
        )
    
    def merge(self, local: StateSnapshot, remote: StateSnapshot) -> StateSnapshot:
        """合并冲突"""
        # 简化实现：remote 覆盖 local
        merged_data = {**local.data, **remote.data}
        return StateSnapshot(
            node_id=self.node_id,
            version=max(local.version, remote.version) + 1,
            data=merged_data,
        )
    
    def get_version(self) -> int:
        """获取当前版本"""
        return self.version
    
    def get_node_status(self, node_id: str) -> NodeStatus:
        """获取节点状态"""
        return self.nodes.get(node_id, NodeStatus.OFFLINE)
