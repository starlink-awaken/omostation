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
# Raft Config Manager ≡ Manager
# 内涵 ≝ {Raft, Config, Manager}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, RaftConfigManager)}
# 功能 ⊢ {Raft_Config, Config_Manager, Manager_Init}
# =============================================================================

"""
---
Type: Organ
Layer: L3
Domain: D-Gateway
Status: ACTIVE
Updated: "2026-04-02"
Summary: Raft-based distributed configuration consensus
---

Raft Config Manager - Raft分布式配置管理

使用Raft算法实现配置变更的分布式共识，确保多节点环境下配置一致性。
"""

import asyncio  # noqa: E402
import json  # noqa: E402
import logging  # noqa: E402
from dataclasses import dataclass, field  # noqa: E402
from pathlib import Path  # noqa: E402
from typing import Any  # noqa: E402

logger = logging.getLogger(__name__)


@dataclass
class RaftLogEntry:
    """Raft日志条目"""

    term: int
    index: int
    command: str  # 'config_update', 'node_add', etc.
    data: dict[str, Any]
    timestamp: float = field(default_factory=lambda: asyncio.get_event_loop().time())


@dataclass
class RaftNodeState:
    """Raft节点状态"""

    node_id: str
    # 角色: follower, candidate, leader
    role: str = "follower"
    current_term: int = 0
    voted_for: str | None = None
    log: list[RaftLogEntry] = field(default_factory=list)
    commit_index: int = 0
    last_applied: int = 0

    # Leader状态
    next_index: dict[str, int] = field(default_factory=dict)
    match_index: dict[str, int] = field(default_factory=dict)


class RaftConfigManager:
    """Raft配置管理器

    使用Raft算法实现配置变更的分布式共识。

    Example:
        >>> manager = RaftConfigManager(node_id="node-1", peers=["node-2", "node-3"])
        >>> await manager.start()
        >>> success = await manager.propose_config_change({"timeout": 30})
    """

    # Raft时间常量
    HEARTBEAT_INTERVAL = 0.1  # 100ms
    ELECTION_TIMEOUT_MIN = 0.15  # 150ms
    ELECTION_TIMEOUT_MAX = 0.3  # 300ms

    def __init__(
        self,
        node_id: str,
        peers: list[str],
        data_dir: str = "data/raft",
        bind_address: str = "0.0.0.0",  # noqa: S104
        port: int = 18000,
    ) -> None:
        self.status = "active"
        self.node_id = node_id
        self.peers = peers
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.bind_address = bind_address
        self.port = port

        self.state = RaftNodeState(node_id=node_id)
        self.all_nodes = {node_id} | set(peers)

        # 运行时状态
        self._running = False
        self._election_timer: asyncio.Task | None = None
        self._heartbeat_task: asyncio.Task | None = None
        self._apply_task: asyncio.Task | None = None

        # 配置存储
        self._config: dict[str, Any] = {}
        self._config_file = self.data_dir / f"config_{node_id}.json"
        self._load_config()

        # 回调
        self._config_change_callbacks: list[callable] = []

    def _load_config(self) -> None:
        """加载本地配置"""
        if self._config_file.exists():
            try:
                with open(self._config_file) as f:
                    self._config = json.load(f)
            except (OSError, json.JSONDecodeError, ValueError) as e:
                logger.error(f"Failed to load config: {e}")
                self._config = {}

    def _save_config(self) -> None:
        """保存本地配置"""
        try:
            with open(self._config_file, "w") as f:
                json.dump(self._config, f, indent=2)
        except (OSError, TypeError) as e:
            logger.error(f"Failed to save config: {e}")

    async def start(self) -> None:
        """启动Raft节点"""
        if self._running:
            return

        self._running = True
        logger.info(f"[Raft] Node {self.node_id} starting...")

        # 启动各个任务
        self._election_timer = asyncio.create_task(self._election_timer_loop())
        self._apply_task = asyncio.create_task(self._apply_loop())

        # 如果是单节点，直接成为leader
        if len(self.all_nodes) == 1:
            self._become_leader()

        logger.info(f"[Raft] Node {self.node_id} started as {self.state.role}")

    async def stop(self) -> None:
        """停止Raft节点"""
        self._running = False

        # 取消所有任务
        for task in [self._election_timer, self._heartbeat_task, self._apply_task]:
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        logger.info(f"[Raft] Node {self.node_id} stopped")

    async def propose_config_change(self, config_update: dict[str, Any]) -> bool:
        """提议配置变更

        只有Leader可以接受配置变更提议。

        Args:
            config_update: 配置更新内容

        Returns:
            bool: 是否成功提交
        """
        if self.state.role != "leader":
            logger.warning("[Raft] Not leader, cannot propose config change")
            return False

        # 创建日志条目
        entry = RaftLogEntry(
            term=self.state.current_term,
            index=len(self.state.log) + 1,
            command="config_update",
            data=config_update,
        )

        # 追加到本地日志
        self.state.log.append(entry)

        # 复制到多数节点
        success = await self._replicate_log_entry(entry)

        if success:
            # 提交日志
            self.state.commit_index = entry.index
            logger.info(f"[Raft] Config change committed at index {entry.index}")
            return True
        else:
            logger.warning("[Raft] Failed to replicate config change")
            return False

    async def get_config(self) -> dict[str, Any]:
        """获取当前配置"""
        return self._config.copy()

    def register_config_change_callback(self, callback: callable) -> None:
        """注册配置变更回调"""
        self._config_change_callbacks.append(callback)

    # ------------------- Raft核心逻辑 -------------------

    def _become_leader(self) -> None:
        """成为Leader"""
        self.state.role = "leader"

        # 初始化Leader状态
        for node in self.all_nodes:
            if node != self.node_id:
                self.state.next_index[node] = len(self.state.log) + 1
                self.state.match_index[node] = 0

        # 启动心跳任务
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

        logger.info(
            f"[Raft] Node {self.node_id} became leader for term {self.state.current_term}"
        )

    def _become_follower(self, term: int) -> None:
        """成为Follower"""
        was_leader = self.state.role == "leader"
        self.state.role = "follower"
        self.state.current_term = term
        self.state.voted_for = None

        # 停止心跳任务
        if was_leader and self._heartbeat_task:
            self._heartbeat_task.cancel()
            self._heartbeat_task = None

        logger.info(f"[Raft] Node {self.node_id} became follower for term {term}")

    def _become_candidate(self) -> None:
        """成为Candidate"""
        self.state.role = "candidate"
        self.state.current_term += 1
        self.state.voted_for = self.node_id

        logger.info(
            f"[Raft] Node {self.node_id} became candidate for term {self.state.current_term}"
        )

    async def _election_timer_loop(self) -> None:
        """选举定时器循环"""
        while self._running:
            # 随机超时时间
            timeout = self.ELECTION_TIMEOUT_MIN + (hash(self.node_id) % 1000 / 1000) * (
                self.ELECTION_TIMEOUT_MAX - self.ELECTION_TIMEOUT_MIN
            )

            await asyncio.sleep(timeout)

            # 检查是否需要发起选举
            if self.state.role != "leader" and self._running:
                await self._start_election()

    async def _start_election(self) -> None:
        """发起选举"""
        self._become_candidate()

        # 给自己投票
        votes = 1

        # 请求其他节点投票（简化版，实际应该发送RPC）
        # 这里使用模拟的投票结果
        for peer in self.peers:
            # 模拟投票请求
            granted = await self._request_vote(peer)
            if granted:
                votes += 1

        # 检查是否获得多数票
        if votes > len(self.all_nodes) / 2:
            self._become_leader()

    async def _request_vote(self, peer: str) -> bool:
        """向节点请求投票"""
        # 简化的投票逻辑，实际应该发送RPC请求
        # 模拟网络延迟
        await asyncio.sleep(0.01)

        # 随机投票结果（简化版）
        # 实际应该基于日志比较决定是否投票
        import random

        return random.random() > 0.3  # 70%概率投票  # noqa: S311

    async def _heartbeat_loop(self) -> None:
        """Leader心跳循环"""
        while self._running and self.state.role == "leader":
            # 发送心跳给所有follower
            for peer in self.peers:
                asyncio.create_task(self._send_heartbeat(peer))

            await asyncio.sleep(self.HEARTBEAT_INTERVAL)

    async def _send_heartbeat(self, peer: str) -> None:
        """发送心跳"""
        # 简化的RPC调用，实际应该发送AppendEntries
        pass  # 心跳保持简单

    async def _replicate_log_entry(self, entry: RaftLogEntry) -> bool:
        """复制日志条目到多数节点"""
        # 简化的复制逻辑
        # 实际应该发送AppendEntries RPC

        success_count = 1  # 自己

        for peer in self.peers:
            # 模拟复制请求
            replicated = await self._send_append_entries(peer, entry)
            if replicated:
                success_count += 1

        # 检查是否复制到多数节点
        return success_count > len(self.all_nodes) / 2

    async def _send_append_entries(self, peer: str, entry: RaftLogEntry) -> bool:
        """发送AppendEntries RPC"""
        # 简化的实现
        await asyncio.sleep(0.01)
        import random

        return random.random() > 0.2  # 80%成功率  # noqa: S311

    async def _apply_loop(self) -> None:
        """应用已提交的日志条目"""
        while self._running:
            while self.state.last_applied < self.state.commit_index:
                self.state.last_applied += 1
                entry = self.state.log[self.state.last_applied - 1]
                await self._apply_entry(entry)

            await asyncio.sleep(0.01)

    async def _apply_entry(self, entry: RaftLogEntry) -> None:
        """应用日志条目"""
        if entry.command == "config_update":
            # 更新配置
            self._config.update(entry.data)
            self._save_config()

            # 触发回调
            for callback in self._config_change_callbacks:
                try:
                    callback(entry.data)
                except (ValueError, TypeError, RuntimeError) as e:
                    logger.error(f"Config change callback error: {e}")

            logger.info(f"[Raft] Applied config update: {entry.data}")

    # ------------------- 状态查询 -------------------

    def is_leader(self) -> bool:
        """当前节点是否是Leader"""
        return self.state.role == "leader"

    def get_status(self) -> dict[str, Any]:
        """获取Raft状态"""
        return {
            "node_id": self.node_id,
            "role": self.state.role,
            "term": self.state.current_term,
            "log_size": len(self.state.log),
            "commit_index": self.state.commit_index,
            "last_applied": self.state.last_applied,
            "peers": self.peers,
        }
