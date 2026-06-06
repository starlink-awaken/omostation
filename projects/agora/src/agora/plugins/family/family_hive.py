from __future__ import annotations

"""
---
Type: Module
Status: ACTIVE
Version: 1.0.0
Authority: nucleus/Z-Core/L0-Genome/R0-ACT-SYS-AX01-10_holographic_metadata_axiom.md
Layer: L3
---
"""
# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Family Hive ≡ Module
# 内涵 ≝ {Family, Hive}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, FamilyHive)}
# 功能 ⊢ {Family_Hive, Init_Family, Validate_Hive}
# =============================================================================

"""
---
Type: FamilyHiveNetwork
Layer: L2
Domain: D-Gateway
Status: ACTIVE
Updated: "2026-04-02"
Authority: 2
Compiled-From: []
Keywords: [family, hive, network, p2p, federation]
---

FamilyHiveNetwork - 联邦网络管理器

实现多节点P2P通信，支持节点发现、心跳维持、消息广播
"""

import asyncio
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any


class NodeRole(StrEnum):
    """节点角色"""

    PRIMARY = "primary"  # 主节点
    SECONDARY = "secondary"  # 从节点
    OBSERVER = "observer"  # 观察者（只读）


class NodeStatus(StrEnum):
    """节点状态"""

    ONLINE = "online"
    OFFLINE = "offline"
    DEGRADED = "degraded"  # 性能降级
    SYNCING = "syncing"  # 同步中


@dataclass
class NodeInfo:
    """节点信息"""

    node_id: str
    role: NodeRole
    endpoint: str  # WebSocket地址 ws://host:port
    public_key: str
    capabilities: list[str] = field(default_factory=list)
    trust_level: float = 0.5  # 0-1
    status: NodeStatus = NodeStatus.OFFLINE
    last_seen: datetime = field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class HiveMessage:
    """Hive网络消息"""

    msg_id: str
    msg_type: str  # heartbeat, broadcast, direct, sync
    source: str  # 源节点ID
    target: str | None  # 目标节点ID（None表示广播）
    payload: dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.utcnow)
    ttl: int = 3  # 跳数限制


class FamilyHiveNetwork:
    """FamilyHive网络管理器

    管理P2P节点网络：
    - 节点发现与加入
    - 心跳维持
    - 消息路由（广播/单播）
    - 状态同步

    拓扑结构：
    ```
    Node A (Primary) <---> Node B (Secondary)
           ^                     ^
           +----------+----------+
                      |
               Node C (Secondary)
    ```
    """

    HEARTBEAT_INTERVAL = 30  # 秒
    OFFLINE_THRESHOLD = 90  # 秒无心跳视为离线

    def __init__(
        self, node_id: str | None = None, role: NodeRole = NodeRole.SECONDARY, endpoint: str = "", public_key: str = ""
    ) -> None:
        """初始化FamilyHive网络

        Args:
            node_id: 节点ID，默认自动生成
            role: 节点角色
            endpoint: 本节点WebSocket地址
            public_key: 本节点公钥
        """
        self.node_id = node_id or str(uuid.uuid4())[:8]
        self.role = role
        self.endpoint = endpoint
        self.public_key = public_key

        # 节点表
        self._nodes: dict[str, NodeInfo] = {}
        self._peers: set[str] = set()  # 已连接节点

        # 消息处理
        self._handlers: dict[str, list[Callable]] = {}
        self._received_msgs: set[str] = set()  # 防重复

        # 运行状态
        self._running = False
        self._tasks: list[asyncio.Task] = []

        # 统计
        self._stats = {"msgs_sent": 0, "msgs_received": 0, "heartbeats_sent": 0, "heartbeats_received": 0}

    # ==================== 网络生命周期 ====================

    async def start(self) -> None:
        """启动网络服务"""
        if self._running:
            return

        self._running = True

        # 启动心跳任务
        heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        self._tasks.append(heartbeat_task)

        # 启动清理任务
        cleanup_task = asyncio.create_task(self._cleanup_loop())
        self._tasks.append(cleanup_task)

        print(f"[FamilyHive] Node {self.node_id} started as {self.role.value}")

    async def stop(self) -> None:
        """停止网络服务"""
        self._running = False

        # 发送离线通知
        await self.broadcast("node_offline", {"node_id": self.node_id})

        # 取消所有任务
        for task in self._tasks:
            task.cancel()

        self._tasks.clear()
        self._peers.clear()

        print(f"[FamilyHive] Node {self.node_id} stopped")

    async def join_network(self, bootstrap_nodes: list[str]) -> bool:
        """加入网络

        Args:
            bootstrap_nodes: 种子节点地址列表

        Returns:
            是否成功加入
        """
        print(f"[FamilyHive] Joining network via {len(bootstrap_nodes)} bootstrap nodes")

        # 尝试连接种子节点
        for endpoint in bootstrap_nodes:
            try:
                # 模拟WebSocket连接
                await self._connect_to_node(endpoint)
            except (OSError, ConnectionError, TimeoutError) as e:
                print(f"[FamilyHive] Failed to connect to {endpoint}: {e}")

        # 只要有连接就认为是成功
        if self._peers:
            # 广播加入消息
            await self.broadcast(
                "node_joined",
                {
                    "node_id": self.node_id,
                    "role": self.role.value,
                    "endpoint": self.endpoint,
                    "capabilities": ["memory_sync", "task_routing"],
                },
            )
            return True

        return False

    # ==================== 消息通信 ====================

    async def broadcast(self, msg_type: str, payload: dict[str, Any], exclude: set[str] | None = None) -> int:
        """广播消息

        Args:
            msg_type: 消息类型
            payload: 消息内容
            exclude: 排除的节点ID集合

        Returns:
            成功发送的节点数
        """
        exclude = exclude or set()
        exclude.add(self.node_id)  # 不发送给自己

        msg = HiveMessage(
            msg_id=str(uuid.uuid4()),
            msg_type=msg_type,
            source=self.node_id,
            target=None,  # 广播
            payload=payload,
            ttl=3,
        )

        sent = 0
        for node_id in self._peers:
            if node_id not in exclude:
                try:
                    await self._send_to_node(node_id, msg)
                    sent += 1
                except (OSError, ConnectionError, TimeoutError) as e:
                    print(f"[FamilyHive] Failed to send to {node_id}: {e}")

        self._stats["msgs_sent"] += sent
        return sent

    async def send_to(self, target_node: str, msg_type: str, payload: dict[str, Any]) -> bool:
        """发送消息到指定节点

        Args:
            target_node: 目标节点ID
            msg_type: 消息类型
            payload: 消息内容

        Returns:
            是否发送成功
        """
        if target_node not in self._nodes:
            print(f"[FamilyHive] Unknown node: {target_node}")
            return False

        msg = HiveMessage(
            msg_id=str(uuid.uuid4()), msg_type=msg_type, source=self.node_id, target=target_node, payload=payload, ttl=3
        )

        try:
            await self._send_to_node(target_node, msg)
            self._stats["msgs_sent"] += 1
            return True
        except (OSError, ConnectionError, TimeoutError) as e:
            print(f"[FamilyHive] Failed to send to {target_node}: {e}")
            return False

    def register_handler(self, msg_type: str, handler: Callable[[HiveMessage], None]) -> None:
        """注册消息处理器"""
        if msg_type not in self._handlers:
            self._handlers[msg_type] = []
        self._handlers[msg_type].append(handler)

    # ==================== 内部方法 ====================

    async def _connect_to_node(self, endpoint: str) -> None:
        """连接到节点（模拟）"""
        # 实际实现：WebSocket连接
        # 这里模拟成功连接
        node_id = f"node_{endpoint.replace(':', '_')}"

        self._nodes[node_id] = NodeInfo(
            node_id=node_id, role=NodeRole.SECONDARY, endpoint=endpoint, public_key="", status=NodeStatus.ONLINE
        )
        self._peers.add(node_id)

        print(f"[FamilyHive] Connected to {node_id} at {endpoint}")

    async def _send_to_node(self, node_id: str, msg: HiveMessage) -> None:
        """发送消息到节点（模拟）"""
        # 实际实现：通过WebSocket发送
        # 这里模拟异步发送
        await asyncio.sleep(0.001)

        # 在真实实现中，这里会通过WebSocket发送
        # 模拟接收方的处理
        print(f"[FamilyHive] Sent {msg.msg_type} to {node_id}")

    async def _heartbeat_loop(self) -> None:
        """心跳循环"""
        while self._running:
            try:
                await self.broadcast(
                    "heartbeat",
                    {"node_id": self.node_id, "timestamp": datetime.now(UTC).isoformat(), "role": self.role.value},
                )
                self._stats["heartbeats_sent"] += 1
            except (OSError, ConnectionError, TimeoutError) as e:
                print(f"[FamilyHive] Heartbeat error: {e}")

            await asyncio.sleep(self.HEARTBEAT_INTERVAL)

    async def _cleanup_loop(self) -> None:
        """清理循环 - 移除离线节点"""
        while self._running:
            now = datetime.now(UTC)
            offline_nodes = []

            for node_id, info in self._nodes.items():
                if now - info.last_seen > timedelta(seconds=self.OFFLINE_THRESHOLD):
                    if info.status == NodeStatus.ONLINE:
                        info.status = NodeStatus.OFFLINE
                        offline_nodes.append(node_id)

            for node_id in offline_nodes:
                self._peers.discard(node_id)
                print(f"[FamilyHive] Node {node_id} marked offline")

            await asyncio.sleep(30)

    async def _handle_incoming_message(self, msg: HiveMessage) -> None:
        """处理收到的消息"""
        # 防重复
        if msg.msg_id in self._received_msgs:
            return
        self._received_msgs.add(msg.msg_id)

        # 更新节点状态
        if msg.source in self._nodes:
            self._nodes[msg.source].last_seen = datetime.now(UTC)
            self._nodes[msg.source].status = NodeStatus.ONLINE

        # 统计
        self._stats["msgs_received"] += 1
        if msg.msg_type == "heartbeat":
            self._stats["heartbeats_received"] += 1

        # 分发到处理器
        handlers = self._handlers.get(msg.msg_type, [])
        for handler in handlers:
            try:
                handler(msg)
            except (OSError, ValueError, RuntimeError, KeyError) as e:
                print(f"[FamilyHive] Handler error: {e}")

        # 广播转发（如果TTL > 0且是广播消息）
        if msg.target is None and msg.ttl > 1:
            msg.ttl -= 1
            await self.broadcast(msg.msg_type, msg.payload, exclude={msg.source})

    # ==================== 查询接口 ====================

    def get_peers(self, online_only: bool = True) -> list[NodeInfo]:
        """获取节点列表"""
        nodes = [self._nodes[nid] for nid in self._peers]
        if online_only:
            nodes = [n for n in nodes if n.status == NodeStatus.ONLINE]
        return nodes

    def get_stats(self) -> dict[str, Any]:
        """获取统计信息"""
        return {
            **self._stats,
            "nodes_total": len(self._nodes),
            "peers_connected": len(self._peers),
            "node_id": self.node_id,
            "role": self.role.value,
        }
