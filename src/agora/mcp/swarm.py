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
LEADER_ELECTION_MSG = b"AGORA_SWARM_ELECT"


# ── 节点健康等级 (Kubernetes/Consul 风格) ──
class NodeHealth:
    GREEN = "green"  # 完全健康
    YELLOW = "yellow"  # 负载较高但可用
    RED = "red"  # 不可用/离线


# ── Gossip 种子节点 ──
GOSSIP_FANOUT = 3  # 每次传播目标数
GOSSIP_INTERVAL = 2  # 传播间隔

# ── 节点模型 ──


@dataclass
class SwarmNode:
    """蜂群中的一个节点。"""

    node_id: str
    host: str
    port: int = SWARM_DEFAULT_PORT
    role: str = "worker"
    bos_uris: list[str] = field(default_factory=list)
    capabilities: dict[str, Any] = field(default_factory=dict)
    last_heartbeat: float = 0.0
    status: str = "unknown"
    # ── P55-W1: 负载感知 (Consul/K8s 风格) ──
    load_score: float = 0.0  # 0-100, 越低越好
    cpu_percent: float = 0.0
    memory_mb: float = 0.0
    queue_depth: int = 0  # 待处理任务数
    generation: int = 0  # 选举 generation (用于 RAFT)

    @property
    def is_online(self) -> bool:
        return time.time() - self.last_heartbeat < HEARTBEAT_TIMEOUT

    @property
    def health(self) -> str:
        """节点健康等级 (GREEN/YELLOW/RED)。"""
        if not self.is_online:
            return NodeHealth.RED
        if self.load_score > 80 or self.queue_depth > 10:
            return NodeHealth.YELLOW
        return NodeHealth.GREEN

    def to_dict(self) -> dict:
        return {
            "node_id": self.node_id,
            "host": self.host,
            "port": self.port,
            "role": self.role,
            "bos_uris": self.bos_uris,
            "status": self.health,
            "load_score": self.load_score,
            "queue_depth": self.queue_depth,
            "generation": self.generation,
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
            self._start_election_timer()
            _log.info("SwarmOrchestrator: master started on port %d", self.port)
        else:
            self._start_heartbeat_sender()
            _log.info("SwarmOrchestrator: %s started", self.role)

        # 所有节点参与 gossip
        self._start_gossip_loop()

    def stop(self) -> None:
        """停止蜂群协调器。"""
        self._running = False
        if self._socket:
            self._socket.close()

    # ── 节点管理 ──

    def register_node(self, node: SwarmNode) -> None:
        """注册一个节点 (手动注册)。"""
        self._nodes[node.node_id] = node
        _log.info(
            "Swarm: node registered: %s (%s, %d BOS URIs)",
            node.node_id,
            node.role,
            len(node.bos_uris),
        )

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
        """根据 BOS URI 查找能处理它的节点（负载感知）。

        规则:
          1. 最长前缀匹配 (与现有逻辑相同)
          2. 同 URI 多节点 → 选负载最低的 (Consul/K8s 风格)
          3. 跳过 RED 节点
          4. YELLOW 节点降权
        """
        candidates: list[tuple[SwarmNode, int]] = []

        for node in self.get_online_nodes():
            if node.health == NodeHealth.RED:
                continue

            for node_uri in node.bos_uris:
                if uri.startswith(node_uri):
                    match_len = len(node_uri)
                    # YELLOW 节点降权: 前缀长度减半
                    if node.health == NodeHealth.YELLOW:
                        match_len = max(1, match_len // 2)
                    candidates.append((node, match_len))

        if not candidates:
            return None

        # 最长前缀匹配; 平局时选负载最低的
        candidates.sort(key=lambda x: (-x[1], x[0].load_score))
        return candidates[0][0]

    # ── Gossip 协议 (Serf/Consul 风格) ──

    def gossip_sync(self) -> None:
        """Gossip 一轮: 随机选 GOSSIP_FANOUT 个节点同步状态，push-pull 合并。"""
        online = self.get_online_nodes()
        if len(online) <= 1:
            return

        import random

        targets = random.sample(online, min(GOSSIP_FANOUT, len(online)))

        for target in targets:
            if target.node_id == self.node_id:
                continue
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.settimeout(1.0)
                msg = json.dumps(
                    {
                        "type": "gossip",
                        "from": self.node_id,
                        "nodes": {
                            nid: n.to_dict()
                            for nid, n in self._nodes.items()
                            if n.is_online
                        },
                        "generation": getattr(self, "_generation", 0),
                    }
                ).encode()
                sock.sendto(msg, (target.host, target.port))
                _log.debug("[Gossip] → %s (%d nodes)", target.node_id, len(self._nodes))
                sock.close()
            except OSError:
                pass

    def _start_gossip_loop(self) -> None:
        """Gossip 后台循环 (master + worker 均参与)。"""

        def _loop():
            while self._running:
                self.gossip_sync()
                time.sleep(GOSSIP_INTERVAL)

        t = threading.Thread(target=_loop, daemon=True)
        t.start()
        _log.info(
            "[Gossip] loop started (fanout=%d, interval=%ds)",
            GOSSIP_FANOUT,
            GOSSIP_INTERVAL,
        )

    # ── Leader Election (RAFT 简化版, 优先级制) ──

    def elect_leader(self) -> str | None:
        """基于优先级的简易选举: master 优先 > 最低 load_score > 最大 generation。

        返回新 leader 的 node_id，或 None（无变化）。
        """
        online = self.get_online_nodes()
        candidates = [n for n in online if n.health != NodeHealth.RED]

        if not candidates:
            return None

        # 排序: master 角色优先 → 负载最低 → generation 最大
        def election_score(node: SwarmNode) -> tuple:
            role_priority = 0 if node.role == "master" else 1
            return (role_priority, node.load_score, -node.generation)

        candidates.sort(key=election_score)
        new_leader = candidates[0]

        # 如果当前节点不是 leader 且 new_leader 不是自己，承认新 leader
        if new_leader.node_id != self.node_id:
            self.role = "worker"
            _log.info("[Election] new leader: %s", new_leader.node_id)
            return new_leader.node_id
        return None

    def _start_election_timer(self) -> None:
        """定期触发选举 (仅 master 角色参与)。"""

        def _timer():
            while self._running:
                time.sleep(HEARTBEAT_TIMEOUT * 2)  # 30s 选举一次
                if self.role == "master":
                    leader = self.elect_leader()
                    if leader and leader != self.node_id:
                        self.role = "worker"  # 降级

        t = threading.Thread(target=_timer, daemon=True)
        t.start()

    # ── 健康等级上报 ──

    def report_load(
        self,
        load_score: float = 0,
        queue_depth: int = 0,
        cpu_pct: float = 0,
        memory_mb: float = 0,
    ) -> None:
        """本节点负载上报 (供 worker heartbeat 使用)。"""
        self_node = self._nodes.get(self.node_id)
        if self_node:
            self_node.load_score = load_score
            self_node.queue_depth = queue_depth
            self_node.cpu_percent = cpu_pct
            self_node.memory_mb = memory_mb

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
                            info = json.loads(data[len(DISCOVERY_MSG) :])
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
                            sock.sendto(
                                RESPONSE_MSG
                                + json.dumps(
                                    {
                                        "master_node_id": self.node_id,
                                        "master_host": socket.gethostname(),
                                        "master_port": self.port,
                                    }
                                ).encode(),
                                addr,
                            )
                            _log.info(
                                "Swarm: discovered %s at %s", node.node_id, addr[0]
                            )
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
                    msg = (
                        DISCOVERY_MSG
                        + json.dumps(
                            {
                                "node_id": self.node_id,
                                "role": self.role,
                                "port": self.port,
                                "bos_uris": getattr(self, "_bos_uris", []),
                            }
                        ).encode()
                    )
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
                        _log.warning(
                            "Swarm: node offline: %s (last heartbeat: %.0fs ago)",
                            node_id,
                            time.time() - node.last_heartbeat,
                        )
                        # 触发 failover: 重新分配该节点的 BOS URI 到其他在线节点
                        if node.bos_uris:
                            _log.info(
                                "Swarm: failover — %d URIs from %s need reassignment",
                                len(node.bos_uris),
                                node_id,
                            )
                time.sleep(HEARTBEAT_INTERVAL)

        self._heartbeat_thread = threading.Thread(target=_monitor, daemon=True)
        self._heartbeat_thread.start()


# ── 全局单例 ──
_swarm: SwarmOrchestrator | None = None


def get_swarm(
    role: str = "worker", port: int = SWARM_DEFAULT_PORT
) -> SwarmOrchestrator:
    global _swarm
    if _swarm is None:
        _swarm = SwarmOrchestrator(role=role, port=port)
    return _swarm
