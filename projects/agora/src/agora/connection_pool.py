"""Connection pool and token-bucket rate limiter.

Extracted from SharedBrain D_Gateway.  Self-contained async utilities
with no nucleus dependencies.

Provides:
- ``ConnectionPool``: async connection pool with reuse and idle cleanup
- ``TokenBucket``: token-bucket rate limiter for flow control
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Connection:
    """连接对象"""

    id: str
    host: str
    port: int
    created_at: float = field(default_factory=time.time)
    last_used: float = field(default_factory=time.time)
    in_use: bool = False

    def mark_used(self) -> None:
        """标记为使用中"""
        self.in_use = True
        self.last_used = time.time()

    def mark_free(self) -> None:
        """标记为空闲"""
        self.in_use = False
        self.last_used = time.time()


class ConnectionPool:
    """异步连接池

    管理有限数量的连接，支持连接复用和超时回收。

    Args:
        max_size: 最大连接数
        max_idle_time: 连接最大空闲时间（秒）
        acquire_timeout: 获取连接超时时间（秒）
    """

    def __init__(
        self,
        max_size: int = 50,
        max_idle_time: float = 300.0,
        acquire_timeout: float = 10.0,
    ) -> None:
        self.max_size = max_size
        self.max_idle_time = max_idle_time
        self.acquire_timeout = acquire_timeout

        self._pool: dict[str, Connection] = {}
        self._available: asyncio.Queue[str] = asyncio.Queue()
        self._semaphore = asyncio.Semaphore(max_size)
        self._lock = asyncio.Lock()
        self._counter = 0

        # 启动清理任务
        self._cleanup_task: asyncio.Task | None = None

    async def start(self) -> None:
        """启动连接池"""
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def stop(self) -> None:
        """停止连接池"""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        # 清空连接池
        async with self._lock:
            self._pool.clear()
            while not self._available.empty():
                try:
                    self._available.get_nowait()
                except asyncio.QueueEmpty:
                    break

    async def acquire(self, host: str, port: int) -> Connection:
        """获取连接

        Args:
            host: 目标主机
            port: 目标端口

        Returns:
            Connection: 连接对象

        Raises:
            asyncio.TimeoutError: 获取连接超时
        """
        # 使用信号量限制总连接数
        async with self._semaphore:
            conn = await self._get_or_create_connection(host, port)
            conn.mark_used()
            return conn

    async def release(self, conn: Connection) -> None:
        """释放连接回池

        Args:
            conn: 要释放的连接
        """
        conn.mark_free()
        await self._available.put(conn.id)

    async def _get_or_create_connection(self, host: str, port: int) -> Connection:
        """获取现有连接或创建新连接"""
        # 首先尝试复用空闲连接
        async with self._lock:
            # 检查是否有到同一目标的空闲连接
            for _conn_id, conn in self._pool.items():
                if not conn.in_use and conn.host == host and conn.port == port:
                    return conn

            if len(self._pool) < self.max_size:
                self._counter += 1
                conn_id = f"conn-{self._counter}"
                conn = Connection(id=conn_id, host=host, port=port)
                self._pool[conn_id] = conn
                return conn

        # 连接池已满时，等待可复用的连接槽
        try:
            conn_id = await asyncio.wait_for(self._available.get(), timeout=self.acquire_timeout)
            async with self._lock:
                if conn_id in self._pool:
                    conn = self._pool[conn_id]
                    conn.host = host
                    conn.port = port
                    return conn
        except TimeoutError:
            raise
        raise RuntimeError("Connection pool signaled an available slot but no connection was found.")

    async def _cleanup_loop(self) -> None:
        """清理过期连接的后台任务"""
        while True:
            try:
                await asyncio.sleep(60)  # 每分钟检查一次
                await self._cleanup_idle_connections()
            except asyncio.CancelledError:
                break
            except (OSError, RuntimeError):
                await asyncio.sleep(10)  # 出错后等待10秒重试

    async def _cleanup_idle_connections(self) -> None:
        """清理空闲时间过长的连接"""
        now = time.time()
        to_remove: set[str] = set()

        async with self._lock:
            for conn_id, conn in self._pool.items():
                if not conn.in_use and (now - conn.last_used) > self.max_idle_time:
                    to_remove.add(conn_id)

            for conn_id in to_remove:
                del self._pool[conn_id]

    def get_stats(self) -> dict[str, Any]:
        """获取连接池统计信息"""
        total = len(self._pool)
        in_use = sum(1 for c in self._pool.values() if c.in_use)
        available = total - in_use

        return {
            "total_connections": total,
            "in_use": in_use,
            "available": available,
            "max_size": self.max_size,
            "utilization": in_use / self.max_size if self.max_size > 0 else 0,
        }


class TokenBucket:
    """令牌桶限流器

    用于限制操作速率，如UDP广播频率。

    Args:
        capacity: 桶容量（最大突发流量）
        fill_rate: 填充速率（令牌/秒）
    """

    def __init__(self, capacity: float, fill_rate: float) -> None:
        self.capacity = capacity
        self.fill_rate = fill_rate
        self.tokens = capacity
        self.last_update = time.monotonic()
        self._lock = asyncio.Lock()

    async def consume(self, amount: float = 1.0) -> bool:
        """尝试消费令牌

        Args:
            amount: 要消费的令牌数

        Returns:
            bool: 是否成功消费
        """
        async with self._lock:
            now = time.monotonic()
            # 补充令牌
            self.tokens = min(
                self.capacity,
                self.tokens + (now - self.last_update) * self.fill_rate,
            )
            self.last_update = now

            if self.tokens >= amount:
                self.tokens -= amount
                return True
            return False

    async def wait_and_consume(self, amount: float = 1.0) -> None:
        """等待并消费令牌（阻塞直到成功）"""
        while not await self.consume(amount):
            # 计算需要等待的时间
            tokens_needed = amount - self.tokens
            wait_time = tokens_needed / self.fill_rate
            await asyncio.sleep(max(0.01, wait_time))
