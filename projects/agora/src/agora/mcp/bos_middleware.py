"""BOS 中间件 — 限流 / 熔断 / 缓存 (P46 W0)
=============================================
提供 BOS URI 调用的可靠性保护层。

用法:
    from agora.mcp.bos_middleware import bos_rate_limiter, bos_circuit_breaker, bos_cache

    # 限流检查
    if not bos_rate_limiter.acquire("bos://memory/kos/search"):
        return _error("Rate limit exceeded")

    # 熔断检查
    if bos_circuit_breaker.is_open("bos://memory/kos/search"):
        return _error("Circuit breaker open")

    # 缓存查询
    hit = bos_cache.get("bos://memory/kos/search", {"query": "eCOS"})
    if hit:
        return hit

    # 缓存写入
    bos_cache.set("bos://memory/kos/search", {"query": "eCOS"}, result, ttl=30)
"""

from __future__ import annotations

import time
import threading
import hashlib
import json
import logging
from typing import Any

_log = logging.getLogger(__name__)


class RateLimiter:
    """滑动窗口限流器。

    每个 BOS URI 独立的请求窗口。
    """

    def __init__(self, default_qps: int = 10, window_s: float = 1.0):
        self._qps: dict[str, int] = {}       # uri → max requests per window
        self._windows: dict[str, tuple[float, int]] = {}  # uri → (window_start, count)
        self._default_qps = default_qps
        self._window_s = window_s

    def configure(self, uri_pattern: str, qps: int) -> None:
        """为 URI 模式配置 QPS 上限。"""
        self._qps[uri_pattern] = qps

    def acquire(self, uri: str) -> bool:
        """尝试获取一个请求槽位。返回 True=允许, False=限流。"""
        # 查找匹配的 QPS 配置 (最长前缀匹配)
        qps = self._default_qps
        for pattern, limit in self._qps.items():
            if uri.startswith(pattern) and len(pattern) > 0:
                qps = limit
        # 滑动窗口
        now = time.time()
        window_key = self._match_key(uri)
        wstart, count = self._windows.get(window_key, (now, 0))
        if now - wstart > self._window_s:
            wstart = now
            count = 0
        if count >= qps:
            return False
        self._windows[window_key] = (wstart, count + 1)
        return True

    def status(self, uri: str = "") -> dict:
        """查询限流状态。"""
        if uri:
            wstart, count = self._windows.get(self._match_key(uri), (0, 0))
            return {"uri": uri, "window_start": wstart, "count": count}
        return {"configured_qps": dict(self._qps), "active_windows": len(self._windows)}

    @staticmethod
    def _match_key(uri: str) -> str:
        parts = uri.split("/")
        return "/".join(parts[:4]) if len(parts) >= 4 else uri  # bos://domain/package


class CircuitBreaker:
    """简单熔断器。

    规则: 连续 N 次失败 → OPEN (拒绝请求)
         静默期后 → HALF_OPEN (探测一次)
         探测成功 → CLOSED (恢复)
    """

    OPEN = "open"
    HALF_OPEN = "half_open"
    CLOSED = "closed"

    def __init__(self, failure_threshold: int = 3, recovery_timeout: float = 30.0):
        self._states: dict[str, dict] = {}  # uri → {state, failures, last_failure_time}
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout
        self._stop_event = threading.Event()
        self._recovery_thread = threading.Thread(target=self._recovery_loop, daemon=True)
        self._recovery_thread.start()

    def _recovery_loop(self) -> None:
        """后台线程: 定期检查 OPEN 电路是否超时，超时则转为 HALF_OPEN。"""
        while not self._stop_event.wait(timeout=self._recovery_timeout):
            for key in list(self._states.keys()):
                s = self._states.get(key)
                if s and s["state"] == self.OPEN:
                    if time.time() - s["last_failure_time"] > self._recovery_timeout:
                        s["state"] = self.HALF_OPEN
                        _log.info("circuit_breaker_half_open for %s (auto)", key)

    def shutdown(self) -> None:
        """停止恢复线程。"""
        self._stop_event.set()

    def is_open(self, uri: str) -> bool:
        """检查熔断是否打开。"""
        key = self._match_key(uri)
        if key not in self._states:
            return False
        s = self._states[key]
        if s["state"] == self.OPEN:
            # 检查恢复超时
            if time.time() - s["last_failure_time"] > self._recovery_timeout:
                s["state"] = self.HALF_OPEN
                _log.info("circuit_breaker_half_open for %s", key)
                return False
            return True
        return False

    def record_success(self, uri: str) -> None:
        """记录成功 — 恢复/维持 CLOSED。"""
        key = self._match_key(uri)
        self._states[key] = {"state": self.CLOSED, "failures": 0, "last_failure_time": 0}

    def record_failure(self, uri: str) -> None:
        """记录失败 — 可能触发 OPEN。"""
        key = self._match_key(uri)
        if key not in self._states:
            self._states[key] = {"state": self.CLOSED, "failures": 1, "last_failure_time": time.time()}
        else:
            s = self._states[key]
            s["failures"] += 1
            s["last_failure_time"] = time.time()
            if s["failures"] >= self._failure_threshold:
                s["state"] = self.OPEN
                _log.warning("circuit_breaker_open for %s (failures=%d)", key, s["failures"])

    def status(self, uri: str = "") -> dict:
        """查询熔断状态。"""
        if uri:
            key = self._match_key(uri)
            return {key: self._states.get(key, {"state": self.CLOSED, "failures": 0})}
        return {k: v for k, v in self._states.items()}

    @staticmethod
    def _match_key(uri: str) -> str:
        parts = uri.split("/")
        return "/".join(parts[:4]) if len(parts) >= 4 else uri


class Cache:
    """内存 TTL 缓存 (用于 BOS 读操作)。

    用法:
        cache.get(uri, params) → result | None
        cache.set(uri, params, result, ttl=30)
    """

    def __init__(self):
        self._store: dict[str, tuple[float, Any]] = {}  # key → (expires_at, value)

    def _key(self, uri: str, params: dict | None = None) -> str | None:
        """生成缓存键: MD5(uri + sorted params). 序列化失败返回 None。"""
        raw = uri
        if params:
            try:
                raw += json.dumps(params, sort_keys=True)
            except (TypeError, ValueError):
                _log.warning("cache_key_serialization_failed for %s", uri)
                return None
        return hashlib.md5(raw.encode()).hexdigest()

    def get(self, uri: str, params: dict | None = None) -> Any | None:
        """查询缓存。返回 None 表示未命中。"""
        key = self._key(uri, params)
        if key is None:
            return None
        entry = self._store.get(key)
        if entry is None:
            return None
        expires, value = entry
        if time.time() > expires:
            del self._store[key]
            return None
        _log.debug("cache_hit for %s", key[:8])
        return value

    def set(self, uri: str, params: dict | None, value: Any, ttl: float = 30.0) -> None:
        """写入缓存。序列化失败则跳过。"""
        key = self._key(uri, params)
        if key is None:
            return
        self._store[key] = (time.time() + ttl, value)

    def invalidate(self, uri: str) -> None:
        """失效 URI 相关的所有缓存。"""
        prefix = hashlib.md5(uri.encode()).hexdigest()[:8]
        keys = [k for k in self._store if k.startswith(prefix)]
        for k in keys:
            del self._store[k]
        _log.info("cache_invalidated for %s (%d keys)", uri, len(keys))

    def status(self) -> dict:
        """缓存状态。"""
        now = time.time()
        active = sum(1 for exp, _ in self._store.values() if exp > now)
        expired = len(self._store) - active
        return {"active_entries": active, "expired_entries": expired, "total": len(self._store)}


# ── 全局单例 ──
bos_rate_limiter = RateLimiter()
bos_circuit_breaker = CircuitBreaker()
bos_cache = Cache()


# ═══════════════════════════════════════════════════════════════
# RetryPolicy (P47)
# ═══════════════════════════════════════════════════════════════

class RetryPolicy:
    """BOS 调用重试策略。

    用法:
        @retry_policy.wrap
        async def call_bos(uri):
            ...
    """

    def __init__(self, max_retries: int = 2, base_delay: float = 0.5):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self._attempts: dict[str, int] = {}

    async def wrap(self, uri: str, coro_func, *args, **kwargs):
        """执行协程，失败时指数退避重试。

        Returns:
            (result, success: bool)
        """
        import asyncio
        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                result = await coro_func(*args, **kwargs)
                key = self._key(uri)
                self._attempts.pop(key, None)
                return (result, True)
            except Exception as e:
                last_error = e
                key = self._key(uri)
                self._attempts[key] = attempt + 1
                if attempt < self.max_retries:
                    delay = self.base_delay * (2 ** attempt)
                    _log.warning("retry_policy: attempt %d/%d for %s, waiting %.1fs",
                               attempt + 1, self.max_retries, uri, delay)
                    await asyncio.sleep(delay)
        return (last_error, False)

    def status(self, uri: str = "") -> dict:
        if uri:
            key = self._key(uri)
            return {uri: {"attempts": self._attempts.get(key, 0)}}
        return {"active_retries": dict(self._attempts)}

    @staticmethod
    def _key(uri: str) -> str:
        parts = uri.split("/")
        return "/".join(parts[:4]) if len(parts) >= 4 else uri


# ── 全局单例 ──
retry_policy = RetryPolicy()


# ═══════════════════════════════════════════════════════════════
# ConfigWatcher (P48) — polling 文件监听
# ═══════════════════════════════════════════════════════════════

class ConfigWatcher:
    """Polling 方式监听配置文件变化，自动 reload。

    用法:
        watcher = ConfigWatcher("/path/to/agora-bos-rates.yaml", on_change=reload_fn)
        watcher.start(interval=5)  # 每 5s 检查一次
    """

    def __init__(self, file_path: str, on_change=None):
        self.file_path = file_path
        self._on_change = on_change
        self._mtime: float = 0
        self._running = False
        self._thread: threading.Thread | None = None

    def start(self, interval: float = 5.0) -> None:
        """启动 polling 监听。"""
        import os
        if os.path.exists(self.file_path):
            self._mtime = os.path.getmtime(self.file_path)
        self._running = True
        self._thread = threading.Thread(target=self._poll_loop, args=(interval,), daemon=True)
        self._thread.start()
        _log.info("config_watcher: watching %s (interval=%ds)", self.file_path, interval)

    def stop(self) -> None:
        """停止监听。"""
        self._running = False

    def _poll_loop(self, interval: float) -> None:
        import os
        while self._running:
            time.sleep(interval)
            try:
                if not os.path.exists(self.file_path):
                    continue
                mtime = os.path.getmtime(self.file_path)
                if mtime != self._mtime:
                    self._mtime = mtime
                    _log.info("config_watcher: file changed, reloading %s", self.file_path)
                    if self._on_change:
                        self._on_change()
            except Exception as e:
                _log.warning("config_watcher: poll error: %s", e)


# ── 全局单例 ──
config_watcher = ConfigWatcher("")  # 延迟配置
