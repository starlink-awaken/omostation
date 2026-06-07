"""Agora Swarm — 多节点蜂群协调层 (P55)

架构:
  Master Node  — 路由表 + 任务分发 + 健康监控
  Worker Node  — 执行 POC Services + 心跳上报
  Function Node — 单服务专注节点 (gbrain/kos/minerva)

通信:
  节点间通过 A2A Task API 通信 (已有 a2a/transport.py)
  心跳: 每 5s UDP 广播 (可降级为 HTTP polling)
  发现: UDP 广播自动发现 + 手动注册

用法:
  启动 Master:  agora-mcp --role master --swarm-port 7455
  启动 Worker:  agora-mcp --role worker --master 192.168.1.100:7455
  启动 Function: agora-mcp --role function --bos-uri bos://memory/gbrain/*

L0: MECH-AGORA-SWARM (Phase 55)
"""

from __future__ import annotations

import json
import logging
import socket
import time
import threading
from dataclasses import dataclass, field
from typing import Any

_log = logging.getLogger(__name__)

# ── 常量 ──
SWARM_DEFAULT_PORT = 7455
HEARTBEAT_INTERVAL = 5  # 秒
HEARTBEAT_TIMEOUT = 15  # 3 个间隔无响应 → 判定离线
DISCOVERY_MSG = b"AGORA_SWARM_DISCOVER"
RESPONSE_MSG = b"AGORA_SWARM_HERE"

# ── 节点模型 ──

@dataclass
class SwarmNode:
    """蜂群中的一个节点。"""
    node_id: str
    host: str
    port: int = SWARM_DEFAULT_PORT
    role: str = "worker"  # master | worker | function
    bos_uris: list[str] = field(default_factory=list)
    capabilities: dict[str, Any] = field(default_factory=dict)
    last_heartbeat: float = 0.0
    status: str = "unknown"  # online | offline | degraded

    @property
    def is_online(self) -> bool:
        return time.time() - self.last_heartbeat < HEARTBEAT_TIMEOUT

    def to_dict(self) -> dict:
        return {
            "node_id": self.node_id,
            "host": self.host,
            "port": self.port,
            "role": self.role,
            "bos_uris": self.bos_uris,
            "capabilities": self.capabilities,
            "status": "online" if self.is_online else "offline",
        }


# ── 蜂群协调器 ──

class SwarmOrchestrator:
    """蜂群主节点协调器。

    职责:
      1. 维护节点注册表
      2. 发现新节点 (UDP 广播)
      3. 健康监控 (心跳超时检测)
      4. BOS 路由表跨节点同步
      5. 任务分发 (根据节点能力路由)
    """

    def __init__(self, role: str = "worker", port: int = SWARM_DEFAULT_PORT):
        self.role = role
        self.port = port
        self.node_id = f"{socket.gethostname()}:{port}:{role}"
        self._nodes: dict[str, SwarmNode] = {}
        self._running = False
        self._discovery_thread: threading.Thread | None = None
        self._heartbeat_thread: threading.Thread | None = None
        self._socket: socket.socket | None = None

    # ── 生命周期 ──

    def start(self) -> None:
        """启动蜂群协调器。"""
        self._running = True

        if self.role == "master":
            self._start_discovery_listener()
            self._start_heartbeat_monitor()
            _log.info("SwarmOrchestrator: master started on port %d", self.port)
        else:
            self._start_heartbeat_sender()
            _log.info("SwarmOrchestrator: %s started", self.role)

    def stop(self) -> None:
        """停止蜂群协调器。"""
        self._running = False
        if self._socket:
            self._socket.close()

    # ── 节点管理 ──

    def register_node(self, node: SwarmNode) -> None:
        """注册一个节点 (手动注册)。"""
        self._nodes[node.node_id] = node
        _log.info("Swarm: node registered: %s (%s, %d BOS URIs)",
                  node.node_id, node.role, len(node.bos_uris))

    def unregister_node(self, node_id: str) -> None:
        """注销节点。"""
        self._nodes.pop(node_id, None)
        _log.info("Swarm: node unregistered: %s", node_id)

    def get_online_nodes(self, role: str = "") -> list[SwarmNode]:
        """获取在线节点列表。"""
        nodes = [n for n in self._nodes.values() if n.is_online]
        if role:
            nodes = [n for n in nodes if n.role == role]
        return nodes

    def get_node_by_uri(self, uri: str) -> SwarmNode | None:
        """根据 BOS URI 查找能处理它的节点。"""
        # 最长前缀匹配
        best = None
        best_len = -1
        for node in self.get_online_nodes():
            for node_uri in node.bos_uris:
                if uri.startswith(node_uri) and len(node_uri) > best_len:
                    best = node
                    best_len = len(node_uri)
        return best

    def status(self) -> dict:
        """蜂群状态摘要。"""
        online = self.get_online_nodes()
        return {
            "node_id": self.node_id,
            "role": self.role,
            "total_nodes": len(self._nodes),
            "online_nodes": len(online),
            "nodes": [n.to_dict() for n in online],
        }

    # ── UDP 发现 ──

    def _start_discovery_listener(self) -> None:
        """UDP 广播监听器 — 接收新节点发现请求。"""
        def _listen():
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.bind(("", self.port))
            sock.settimeout(1.0)

            while self._running:
                try:
                    data, addr = sock.recvfrom(1024)
                    if data.startswith(DISCOVERY_MSG):
                        # 解析节点信息
                        try:
                            info = json.loads(data[len(DISCOVERY_MSG):])
                            node = SwarmNode(
                                node_id=info.get("node_id", f"{addr[0]}:unknown"),
                                host=addr[0],
                                port=info.get("port", self.port),
                                role=info.get("role", "worker"),
                                bos_uris=info.get("bos_uris", []),
                                last_heartbeat=time.time(),
                            )
                            self.register_node(node)
                            # 回复: 告知主节点位置
                            sock.sendto(RESPONSE_MSG + json.dumps({
                                "master_node_id": self.node_id,
                                "master_host": socket.gethostname(),
                                "master_port": self.port,
                            }).encode(), addr)
                            _log.info("Swarm: discovered %s at %s", node.node_id, addr[0])
                        except (json.JSONDecodeError, KeyError):
                            pass
                except socket.timeout:
                    continue
                except OSError:
                    break

        self._discovery_thread = threading.Thread(target=_listen, daemon=True)
        self._discovery_thread.start()

    def _start_heartbeat_sender(self) -> None:
        """心跳发送器 — worker 定期向 master 发送心跳。"""
        def _send():
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.settimeout(1.0)

            while self._running:
                try:
                    msg = DISCOVERY_MSG + json.dumps({
                        "node_id": self.node_id,
                        "role": self.role,
                        "port": self.port,
                        "bos_uris": getattr(self, '_bos_uris', []),
                    }).encode()
                    sock.sendto(msg, ("255.255.255.255", self.port))
                except OSError:
                    pass
                time.sleep(HEARTBEAT_INTERVAL)

        self._heartbeat_thread = threading.Thread(target=_send, daemon=True)
        self._heartbeat_thread.start()

    def _start_heartbeat_monitor(self) -> None:
        """心跳监控器 — master 检测离线节点。"""
        def _monitor():
            while self._running:
                for node_id, node in list(self._nodes.items()):
                    if not node.is_online and node.status != "offline":
                        node.status = "offline"
                        _log.warning("Swarm: node offline: %s (last heartbeat: %.0fs ago)",
                                    node_id, time.time() - node.last_heartbeat)
                        # 触发 failover: 重新分配该节点的 BOS URI 到其他在线节点
                        if node.bos_uris:
                            _log.info("Swarm: failover — %d URIs from %s need reassignment",
                                     len(node.bos_uris), node_id)
                time.sleep(HEARTBEAT_INTERVAL)

        self._heartbeat_thread = threading.Thread(target=_monitor, daemon=True)
        self._heartbeat_thread.start()


# ── 全局单例 ──
_swarm: SwarmOrchestrator | None = None


def get_swarm(role: str = "worker", port: int = SWARM_DEFAULT_PORT) -> SwarmOrchestrator:
    global _swarm
    if _swarm is None:
        _swarm = SwarmOrchestrator(role=role, port=port)
    return _swarm
