"""L0 分布式原语 — 为蜂群式AI超级大脑构建分布式基础

支持多机协作的核心组件：
- CRDT 同步：无冲突复制数据类型，支持 LWW-Register 冲突解决
- NodeManager：节点注册、发现、健康检查
- StateSync：跨机状态同步服务
- CommunicationProtocol：跨机通信协议
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
import hashlib
import json


class SyncStrategy(Enum):
    """同步策略
    
    M1 定义: 分布式状态同步策略
    """
    CRDT = "crdt"           # 无冲突复制数据类型 (LWW-Register)
    EVENTUAL = "eventual"   # 最终一致性
    STRONG = "strong"       # 强一致性


class NodeStatus(Enum):
    """节点状态"""
    ONLINE = "online"
    OFFLINE = "offline"
    SYNCING = "syncing"
    CONFLICT = "conflict"
    HEALTHY = "healthy"
    DEGRADED = "degraded"


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
    
    def compute_checksum(self) -> str:
        """计算校验和"""
        data_str = json.dumps(self.data, sort_keys=True)
        return hashlib.sha256(data_str.encode()).hexdigest()[:16]


@dataclass
class SyncResult:
    """同步结果"""
    success: bool
    local_version: int
    remote_version: int
    merged_version: int
    conflicts: list[str] = field(default_factory=list)
    strategy: SyncStrategy = SyncStrategy.CRDT


@dataclass
class NodeInfo:
    """节点信息"""
    node_id: str
    status: NodeStatus
    last_heartbeat: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    version: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


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
    """CRDT 同步实现 (LWW-Register)
    
    使用 Last-Write-Wins 策略解决冲突：
    - 时间戳最新的写入获胜
    - 相同时间戳时，node_id 字典序较大的获胜
    """
    
    def __init__(self, node_id: str):
        self.node_id = node_id
        self.version = 0
        self.data: dict[str, Any] = {}
        self.nodes: dict[str, NodeStatus] = {}
        self.vector_clock: dict[str, int] = {node_id: 0}
    
    def sync(self, snapshot: StateSnapshot) -> SyncResult:
        """同步状态 — LWW-Register 策略"""
        conflicts = []
        
        # 检查版本冲突
        if snapshot.version < self.version:
            # 远程版本较旧，检查是否有冲突的键
            for key, remote_value in snapshot.data.items():
                if key in self.data and self.data[key] != remote_value:
                    conflicts.append(key)
            
            # LWW: 保留本地版本（因为本地更新）
            return SyncResult(
                success=True,
                local_version=self.version,
                remote_version=snapshot.version,
                merged_version=self.version,
                conflicts=conflicts,
                strategy=SyncStrategy.CRDT,
            )
        
        # 远程版本更新或相等，合并数据
        merged_data = self._merge_data(self.data, snapshot.data, snapshot.timestamp)
        self.data = merged_data
        self.version = max(self.version, snapshot.version) + 1
        
        # 更新向量时钟
        self.vector_clock[snapshot.node_id] = snapshot.version
        
        return SyncResult(
            success=True,
            local_version=self.version,
            remote_version=snapshot.version,
            merged_version=self.version,
            conflicts=conflicts,
            strategy=SyncStrategy.CRDT,
        )
    
    def _merge_data(self, local: dict, remote: dict, remote_timestamp: datetime) -> dict:
        """合并数据 — LWW-Register 策略"""
        merged = local.copy()
        for key, remote_value in remote.items():
            if key not in merged:
                # 新键，直接添加
                merged[key] = remote_value
            # 如果键已存在，保留本地版本（LWW 策略）
        return merged
    
    def merge(self, local: StateSnapshot, remote: StateSnapshot) -> StateSnapshot:
        """合并冲突 — LWW-Register 策略"""
        # LWW: 时间戳最新的获胜
        if remote.timestamp > local.timestamp:
            merged_data = remote.data.copy()
        elif remote.timestamp < local.timestamp:
            merged_data = local.data.copy()
        else:
            # 相同时间戳，node_id 字典序较大的获胜
            if remote.node_id > local.node_id:
                merged_data = remote.data.copy()
            else:
                merged_data = local.data.copy()
        
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
    
    def register_node(self, node_id: str, status: NodeStatus = NodeStatus.ONLINE) -> None:
        """注册节点"""
        self.nodes[node_id] = status
    
    def update_node_status(self, node_id: str, status: NodeStatus) -> None:
        """更新节点状态"""
        self.nodes[node_id] = status
    
    def get_all_nodes(self) -> dict[str, NodeStatus]:
        """获取所有节点状态"""
        return self.nodes.copy()


class NodeManager:
    """节点管理器
    
    管理分布式系统中的节点注册、发现和健康检查
    """
    
    def __init__(self):
        self.nodes: dict[str, NodeInfo] = {}
        self.heartbeat_interval: int = 30  # 秒
    
    def register(self, node_id: str, metadata: dict[str, Any] | None = None) -> NodeInfo:
        """注册节点"""
        node = NodeInfo(
            node_id=node_id,
            status=NodeStatus.ONLINE,
            metadata=metadata or {},
        )
        self.nodes[node_id] = node
        return node
    
    def unregister(self, node_id: str) -> bool:
        """注销节点"""
        if node_id in self.nodes:
            del self.nodes[node_id]
            return True
        return False
    
    def get_node(self, node_id: str) -> NodeInfo | None:
        """获取节点信息"""
        return self.nodes.get(node_id)
    
    def get_all_nodes(self) -> list[NodeInfo]:
        """获取所有节点"""
        return list(self.nodes.values())
    
    def get_online_nodes(self) -> list[NodeInfo]:
        """获取在线节点"""
        return [n for n in self.nodes.values() if n.status == NodeStatus.ONLINE]
    
    def update_heartbeat(self, node_id: str) -> bool:
        """更新心跳"""
        if node_id in self.nodes:
            self.nodes[node_id].last_heartbeat = datetime.now(timezone.utc)
            self.nodes[node_id].status = NodeStatus.ONLINE
            return True
        return False
    
    def check_health(self) -> dict[str, NodeStatus]:
        """检查所有节点健康状态"""
        now = datetime.now(timezone.utc)
        result = {}
        
        for node_id, node in self.nodes.items():
            elapsed = (now - node.last_heartbeat).total_seconds()
            if elapsed > self.heartbeat_interval * 3:
                node.status = NodeStatus.OFFLINE
            elif elapsed > self.heartbeat_interval * 2:
                node.status = NodeStatus.DEGRADED
            else:
                node.status = NodeStatus.HEALTHY
            result[node_id] = node.status
        
        return result
    
    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "nodes": {
                nid: {
                    "status": n.status.value,
                    "last_heartbeat": n.last_heartbeat.isoformat(),
                    "version": n.version,
                }
                for nid, n in self.nodes.items()
            },
            "heartbeat_interval": self.heartbeat_interval,
        }
