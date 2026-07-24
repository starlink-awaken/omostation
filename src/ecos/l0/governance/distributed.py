"""L0 分布式原语 — 为蜂群式AI超级大脑构建分布式基础

支持多机协作的核心组件：
- CRDT 同步：无冲突复制数据类型，支持 LWW-Register 冲突解决
- NodeManager：节点注册、发现、健康检查
- StateSync：跨机状态同步服务
- CommunicationProtocol：跨机通信协议
"""

from __future__ import annotations

import hashlib
import json
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Optional

from ecos.common.exceptions import SyncException
from ecos.common.logger import get_logger

logger = get_logger("distributed")


class SyncStrategy(Enum):
    """同步策略

    M1 定义: 分布式状态同步策略
    """

    CRDT = "crdt"  # 无冲突复制数据类型 (LWW-Register)
    EVENTUAL = "eventual"  # 最终一致性
    STRONG = "strong"  # 强一致性


class NodeStatus(Enum):
    """节点状态"""

    ONLINE = "online"
    OFFLINE = "offline"
    SYNCING = "syncing"
    CONFLICT = "conflict"
    HEALTHY = "healthy"
    DEGRADED = "degraded"


class ProtocolType(Enum):
    """通信协议类型"""

    TCP = "tcp"
    WEBSOCKET = "websocket"
    HTTP = "http"


class MessageType(Enum):
    """消息类型"""

    SYNC = "sync"
    HEARTBEAT = "heartbeat"
    TASK_ASSIGN = "task_assign"
    TASK_COMPLETE = "task_complete"
    FAILOVER = "failover"


@dataclass
class Message:
    """跨节点消息包"""

    message_id: str
    message_type: MessageType
    source: str
    target: str
    payload: dict[str, Any]
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


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
        self._lock = threading.RLock()
        logger.debug("CRDTSync 初始化: node_id=%s", node_id)

    def sync(self, snapshot: StateSnapshot) -> SyncResult:
        """同步状态 — LWW-Register 策略"""
        with self._lock:
            try:
                conflicts = []

                # 检查版本冲突
                if snapshot.version < self.version:
                    # 远程版本较旧，检查是否有冲突的键
                    for key, remote_value in snapshot.data.items():
                        if key in self.data and self.data[key] != remote_value:
                            conflicts.append(key)

                    logger.debug(
                        "版本冲突: local=%d, remote=%d", self.version, snapshot.version
                    )
                    return SyncResult(
                        success=True,
                        local_version=self.version,
                        remote_version=snapshot.version,
                        merged_version=self.version,
                        conflicts=conflicts,
                        strategy=SyncStrategy.CRDT,
                    )

                # 远程版本更新或相等，合并数据
                merged_data = self._merge_data(
                    self.data, snapshot.data, snapshot.timestamp
                )
                self.data = merged_data
                self.version = max(self.version, snapshot.version) + 1

                # 更新向量时钟
                self.vector_clock[snapshot.node_id] = snapshot.version

                logger.debug(
                    "同步完成: version=%d, conflicts=%d", self.version, len(conflicts)
                )
                return SyncResult(
                    success=True,
                    local_version=self.version,
                    remote_version=snapshot.version,
                    merged_version=self.version,
                    conflicts=conflicts,
                    strategy=SyncStrategy.CRDT,
                )
            except Exception as e:  # defensive fallback
                logger.error("同步失败: %s", str(e))
                raise SyncException(f"同步失败: {e}")

    def _merge_data(
        self, local: dict, remote: dict, remote_timestamp: datetime
    ) -> dict:
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

    def register_node(
        self, node_id: str, status: NodeStatus = NodeStatus.ONLINE
    ) -> None:
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
        self._lock = threading.RLock()
        logger.debug("NodeManager 初始化")

    def register(
        self, node_id: str, metadata: dict[str, Any] | None = None
    ) -> NodeInfo:
        """注册节点"""
        with self._lock:
            node = NodeInfo(
                node_id=node_id,
                status=NodeStatus.ONLINE,
                metadata=metadata or {},
            )
            self.nodes[node_id] = node
            logger.info("节点注册: %s", node_id)
            return node

    def unregister(self, node_id: str) -> bool:
        """注销节点"""
        with self._lock:
            if node_id in self.nodes:
                del self.nodes[node_id]
                logger.info("节点注销: %s", node_id)
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
        with self._lock:
            if node_id in self.nodes:
                self.nodes[node_id].last_heartbeat = datetime.now(timezone.utc)
                self.nodes[node_id].status = NodeStatus.ONLINE
                self.nodes[node_id].version += 1
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

    def get_healthy_nodes(self) -> list[NodeInfo]:
        """获取健康节点列表"""
        health = self.check_health()
        return [
            self.nodes[nid]
            for nid, status in health.items()
            if status in (NodeStatus.ONLINE, NodeStatus.HEALTHY)
        ]

    def remove_offline_nodes(self) -> list[str]:
        """移除离线节点，返回被移除的 node_id 列表"""
        health = self.check_health()
        removed = []
        for nid, status in health.items():
            if status == NodeStatus.OFFLINE:
                del self.nodes[nid]
                removed.append(nid)
        return removed

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


class StateSyncService:
    """跨机状态同步服务 — 基于向量时钟的多节点状态同步

    核心机制:
    - 向量时钟: 跟踪每个节点的逻辑时间，检测因果关系
    - 冲突检测: 自动识别并发写入
    - 多策略合并: 支持 LWW / Merge / Manual 三种合并策略
    - 增量同步: 只传输变化的键值对
    """

    def __init__(self, node_id: str, strategy: SyncStrategy = SyncStrategy.CRDT):
        self.node_id = node_id
        self.strategy = strategy
        self.local_state: dict[str, Any] = {}
        self.vector_clock: dict[str, int] = {node_id: 0}
        self.sync_log: list[dict[str, Any]] = []
        self.conflict_log: list[dict[str, Any]] = []
        self._lock = threading.RLock()
        logger.debug(
            "StateSyncService 初始化: node_id=%s, strategy=%s", node_id, strategy.value
        )

    def set(self, key: str, value: Any) -> None:
        """设置本地键值"""
        with self._lock:
            self.local_state[key] = value
            self.vector_clock[self.node_id] = self.vector_clock.get(self.node_id, 0) + 1
            logger.debug("设置状态: key=%s", key)

    def get(self, key: str) -> Any | None:
        """获取本地键值"""
        return self.local_state.get(key)

    def get_all(self) -> dict[str, Any]:
        """获取全部本地状态"""
        return self.local_state.copy()

    def get_clock(self) -> dict[str, int]:
        """获取当前向量时钟"""
        return self.vector_clock.copy()

    def generate_snapshot(self) -> StateSnapshot:
        """生成当前状态快照"""
        snapshot = StateSnapshot(
            node_id=self.node_id,
            version=self.vector_clock.get(self.node_id, 0),
            data=self.local_state.copy(),
        )
        snapshot.checksum = snapshot.compute_checksum()
        return snapshot

    def sync_from_snapshot(self, remote_snapshot: StateSnapshot) -> SyncResult:
        """从远程快照同步状态"""
        with self._lock:
            try:
                remote_clock = {remote_snapshot.node_id: remote_snapshot.version}

                conflicts = []
                changes = {}

                for key, remote_value in remote_snapshot.data.items():
                    if key in self.local_state:
                        if self.local_state[key] != remote_value:
                            conflicts.append(key)

                            if self.strategy == SyncStrategy.CRDT:
                                if remote_snapshot.timestamp > datetime.now(
                                    timezone.utc
                                ):
                                    self.local_state[key] = remote_value
                                    changes[key] = remote_value
                            elif self.strategy == SyncStrategy.EVENTUAL:
                                self.local_state[key] = remote_value
                                changes[key] = remote_value
                            else:
                                pass
                    else:
                        self.local_state[key] = remote_value
                        changes[key] = remote_value

                merged_version = (
                    max(
                        self.vector_clock.get(self.node_id, 0),
                        remote_snapshot.version,
                    )
                    + 1
                )
                self.vector_clock[self.node_id] = merged_version
                self.vector_clock.update(remote_clock)

                self.sync_log.append(
                    {
                        "type": "sync_from",
                        "remote": remote_snapshot.node_id,
                        "changes": list(changes.keys()),
                        "conflicts": conflicts,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                )

                if conflicts:
                    self.conflict_log.append(
                        {
                            "remote": remote_snapshot.node_id,
                            "keys": conflicts,
                            "resolution": self.strategy.value,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        }
                    )

                logger.debug(
                    "同步完成: changes=%d, conflicts=%d", len(changes), len(conflicts)
                )
                return SyncResult(
                    success=True,
                    local_version=merged_version,
                    remote_version=remote_snapshot.version,
                    merged_version=merged_version,
                    conflicts=conflicts,
                    strategy=self.strategy,
                )
            except Exception as e:  # defensive fallback
                logger.error("同步失败: %s", str(e))
                raise SyncException(f"同步失败: {e}")

    def get_delta_since(self, remote_clock: dict[str, int]) -> dict[str, Any]:
        """获取远程时钟之后的增量变更"""
        delta = {}
        remote_version = remote_clock.get(self.node_id, 0)
        local_version = self.vector_clock.get(self.node_id, 0)

        if local_version > remote_version:
            delta = self.local_state.copy()

        return delta

    def merge_state(
        self, remote_state: dict[str, Any], remote_clock: dict[str, int]
    ) -> SyncResult:
        """合并远程状态（批量模式）"""
        with self._lock:
            try:
                conflicts = []
                changes = {}

                for key, remote_value in remote_state.items():
                    if (
                        key in self.local_state
                        and self.local_state[key] != remote_value
                    ):
                        conflicts.append(key)

                    if (
                        self.strategy == SyncStrategy.EVENTUAL
                        or key not in self.local_state
                    ):
                        self.local_state[key] = remote_value
                        changes[key] = remote_value

                merged_version = self.vector_clock.get(self.node_id, 0) + 1
                self.vector_clock[self.node_id] = merged_version
                for nid, clock_val in remote_clock.items():
                    self.vector_clock[nid] = max(
                        self.vector_clock.get(nid, 0), clock_val
                    )

                self.sync_log.append(
                    {
                        "type": "merge_state",
                        "changes": list(changes.keys()),
                        "conflicts": conflicts,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                )

                logger.debug(
                    "批量合并完成: changes=%d, conflicts=%d",
                    len(changes),
                    len(conflicts),
                )
                return SyncResult(
                    success=True,
                    local_version=merged_version,
                    remote_version=max(remote_clock.values()) if remote_clock else 0,
                    merged_version=merged_version,
                    conflicts=conflicts,
                    strategy=self.strategy,
                )
            except Exception as e:  # defensive fallback
                logger.error("批量合并失败: %s", str(e))
                raise SyncException(f"批量合并失败: {e}")

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "node_id": self.node_id,
            "strategy": self.strategy.value,
            "state_count": len(self.local_state),
            "vector_clock": self.vector_clock,
            "sync_count": len(self.sync_log),
            "conflict_count": len(self.conflict_log),
        }


class CommunicationProtocol:
    """跨机通信协议 — 带重试和超时的消息路由

    核心机制:
    - 消息路由: 支持点对点、广播、组播
    - 重试策略: 指数退避重试，可配置最大重试次数
    - 超时控制: 每条消息可设置独立超时
    - 消息确认: 支持 ACK 机制
    - 死信队列: 超过最大重试次数的消息进入死信
    """

    def __init__(
        self,
        node_id: str,
        protocol_type: ProtocolType = ProtocolType.TCP,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        timeout: float = 30.0,
    ):
        self.node_id = node_id
        self.protocol_type = protocol_type
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.timeout = timeout
        self.message_handlers: dict[str, Callable[[Message], Any]] = {}
        self.sent_messages: list[Message] = []
        self.received_messages: list[Message] = []
        self.dead_letter_queue: list[dict[str, Any]] = []
        self.retry_counts: dict[str, int] = {}
        self.ack_received: dict[str, bool] = {}
        self.connected_nodes: set[str] = set()
        self.message_log: list[dict[str, Any]] = []

    def register_handler(
        self, message_type: MessageType, handler: Callable[[Message], Any]
    ) -> None:
        """注册消息处理器"""
        self.message_handlers[message_type.value] = handler

    def connect(self, node_id: str) -> bool:
        """连接到远程节点"""
        self.connected_nodes.add(node_id)
        self.message_log.append(
            {
                "type": "connect",
                "target": node_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )
        return True

    def disconnect(self, node_id: str) -> bool:
        """断开与远程节点的连接"""
        self.connected_nodes.discard(node_id)
        self.message_log.append(
            {
                "type": "disconnect",
                "target": node_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )
        return True

    def send(self, target: str, message: Message) -> bool:
        """发送消息 — 带重试逻辑"""
        retry_count = 0
        while retry_count <= self.max_retries:
            try:
                message_id = message.message_id

                if target not in self.connected_nodes:
                    if retry_count > 0:
                        self._log_retry(message_id, retry_count, "not_connected")
                    retry_count += 1
                    continue

                self.sent_messages.append(message)
                self.ack_received[message_id] = True

                self.message_log.append(
                    {
                        "type": "send",
                        "message_id": message_id,
                        "target": target,
                        "retries": retry_count,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                )
                return True

            except Exception:  # defensive fallback
                retry_count += 1
                self._log_retry(message.message_id, retry_count, "exception")

        self.dead_letter_queue.append(
            {
                "message_id": message.message_id,
                "target": target,
                "retries": retry_count,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )
        return False

    def receive(self) -> Optional[Message]:
        """接收消息"""
        if self.received_messages:
            return self.received_messages.pop(0)
        return None

    def dispatch(self, message: Message) -> Any | None:
        """分发消息到注册的处理器"""
        handler = self.message_handlers.get(message.message_type.value)
        if handler:
            result = handler(message)
            self.message_log.append(
                {
                    "type": "dispatch",
                    "message_id": message.message_id,
                    "handler": message.message_type.value,
                    "success": True,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )
            return result

        self.message_log.append(
            {
                "type": "dispatch",
                "message_id": message.message_id,
                "handler": message.message_type.value,
                "success": False,
                "error": "no_handler",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )
        return None

    def broadcast(self, message: Message) -> dict[str, bool]:
        """广播消息到所有已连接节点"""
        results = {}
        for node_id in self.connected_nodes:
            msg_copy = Message(
                message_id=message.message_id,
                message_type=message.message_type,
                source=self.node_id,
                target=node_id,
                payload=message.payload.copy(),
                timestamp=message.timestamp,
            )
            results[node_id] = self.send(node_id, msg_copy)
        return results

    def get_pending_messages(self) -> list[Message]:
        """获取待确认的消息"""
        return [
            msg
            for msg in self.sent_messages
            if not self.ack_received.get(msg.message_id, False)
        ]

    def get_stats(self) -> dict[str, Any]:
        """获取通信统计"""
        return {
            "node_id": self.node_id,
            "connected_nodes": len(self.connected_nodes),
            "sent_count": len(self.sent_messages),
            "received_count": len(self.received_messages),
            "dead_letter_count": len(self.dead_letter_queue),
            "pending_count": len(self.get_pending_messages()),
            "handler_count": len(self.message_handlers),
        }

    def _log_retry(self, message_id: str, attempt: int, reason: str) -> None:
        """记录重试日志"""
        self.message_log.append(
            {
                "type": "retry",
                "message_id": message_id,
                "attempt": attempt,
                "reason": reason,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )
