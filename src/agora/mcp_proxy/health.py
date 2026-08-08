"""BackendHealthChecker — background heartbeat for MCP backends.

Periodically probes all registered backends, marks unresponsive ones as
offline, and optionally auto-removes chronically dead backends.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field

import structlog

logger = structlog.get_logger(__name__)

_HEARTBEAT_DEFAULT_INTERVAL = 30  # seconds
_HEARTBEAT_TIMEOUT = 5  # seconds per probe
_MAX_CONSECUTIVE_FAILURES = 3  # auto-remove after N consecutive failures


@dataclass
class BackendStatus:
    """Runtime health state of a single backend."""

    name: str
    alive: bool = True
    last_ok: float | None = None
    last_fail: float | None = None
    consecutive_failures: int = 0
    last_tool_samples: list[str] = field(default_factory=list)


class BackendHealthChecker:
    """Background heartbeat loop for MCP backend connections.

    Usage:
        checker = BackendHealthChecker(proxy_manager)
        await checker.start()
        # ... run Agora ...
        await checker.stop()
    """

    def __init__(
        self,
        proxy_manager: object,  # ProxyManager instance
        interval: int = _HEARTBEAT_DEFAULT_INTERVAL,
        probe_timeout: int = _HEARTBEAT_TIMEOUT,
        max_failures: int = _MAX_CONSECUTIVE_FAILURES,
    ):
        self._manager = proxy_manager
        self._interval = interval
        self._probe_timeout = probe_timeout
        self._max_failures = max_failures
        self._status: dict[str, BackendStatus] = {}
        self._task: asyncio.Task | None = None
        self._stopped = asyncio.Event()

    # ── Lifecycle ────────────────────────────────────────────────

    async def start(self) -> None:
        if self._task is not None:
            return
        self._stopped.clear()
        self._task = asyncio.create_task(self._loop())
        logger.info("heartbeat_started", interval=self._interval)

    async def stop(self) -> None:
        if self._task is None:
            return
        self._stopped.set()
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None
        logger.info("heartbeat_stopped")

    # ── Status API ───────────────────────────────────────────────

    def get_all_status(self) -> dict[str, dict]:
        """Return heartbeat status for all known backends."""
        return {
            name: {
                "alive": s.alive,
                "last_ok": s.last_ok,
                "last_fail": s.last_fail,
                "consecutive_failures": s.consecutive_failures,
                "tools": s.last_tool_samples[:3],
            }
            for name, s in self._status.items()
        }

    def is_alive(self, name: str) -> bool:
        s = self._status.get(name)
        if s is None:
            return True  # unknown = assume alive
        return s.alive

    def mark_alive(self, name: str) -> None:
        if name not in self._status:
            self._status[name] = BackendStatus(name=name)
        self._status[name].alive = True
        self._status[name].last_ok = time.time()
        self._status[name].consecutive_failures = 0

    def mark_dead(self, name: str) -> None:
        if name not in self._status:
            self._status[name] = BackendStatus(name=name)
        s = self._status[name]
        s.alive = False
        s.last_fail = time.time()
        s.consecutive_failures += 1

    def _is_transient(self, name: str) -> bool:
        """stdio 按需服务 (有 command 无 mcp_endpoint) 调用时才 spawn 进程,
        不该用常驻 heartbeat 验活 — 否则进程不存在必假 dead (ADR-0179 / p76).

        只有 daemon/http/sse (有 mcp_endpoint 的常驻服务) 才参与 heartbeat.
        """
        registry = getattr(self._manager, "registry", None)
        if registry is None:
            return False
        get_cfg = getattr(registry, "get_saved_config", None)
        if get_cfg is None:
            return False
        cfg = get_cfg(name) or {}
        has_command = bool(cfg.get("command"))
        has_endpoint = bool(cfg.get("mcp_endpoint"))
        return has_command and not has_endpoint

    # ── Internal loop ────────────────────────────────────────────

    async def _probe_one(self, name: str) -> None:
        """Probe a single backend by dispatching a no-op tool (if available)
        or by checking the registry for available tools."""
        try:
            # Try to list tools from the backend (lightweight probe)
            registry = getattr(self._manager, "registry", None)
            if registry is None:
                return

            tools_fn = getattr(registry, "get_tools", None)
            if tools_fn:
                tools = tools_fn(name)
                if tools:
                    self.mark_alive(name)
                    self._status[name].last_tool_samples = list(tools)[:3]
                    return

            # Fallback: try dispatching a health tool
            client = getattr(registry, "_clients", {}).get(name)
            if client is None:
                self.mark_dead(name)
                return

            # Check if client connection is responsive via list_tools
            list_t = getattr(client, "list_tools", None)
            if list_t:
                try:
                    result = await asyncio.wait_for(
                        list_t(), timeout=self._probe_timeout
                    )
                    if result is not None:
                        self.mark_alive(name)
                        return
                except Exception:  # defensive fallback
                    pass

            self.mark_dead(name)
        except Exception:  # defensive fallback
            self.mark_dead(name)

    async def _loop(self) -> None:
        while not self._stopped.is_set():
            try:
                await self._tick()
            except asyncio.CancelledError:
                break
            except Exception as e:  # defensive fallback
                logger.warning("heartbeat_tick_error", error=str(e))

            try:
                await asyncio.wait_for(
                    self._stopped.wait(),
                    timeout=self._interval,
                )
                break  # stopped signal received
            except TimeoutError:
                continue  # next tick

    async def _tick(self) -> None:
        """One heartbeat tick: probe all registered backends."""
        registry = getattr(self._manager, "registry", None)
        if registry is None:
            return

        all_backends = getattr(registry, "list_services", None)
        if all_backends is None:
            # Fallback: use _configs from ProxyManager
            all_backends = list(getattr(self._manager, "_configs", {}).keys())
        else:
            all_backends = all_backends()

        if not all_backends:
            return

        # stdio 按需服务 (transient) 调用时才 spawn, 常驻 heartbeat 验活必假 dead;
        # 跳过它们 + 清掉之前误判入 _status 的 transient, 不计入 alive/dead.
        persistent = [n for n in all_backends if not self._is_transient(n)]
        stale_transient = [n for n in list(self._status) if self._is_transient(n)]
        for n in stale_transient:
            del self._status[n]
        if stale_transient:
            logger.info(
                "heartbeat_skip_transient",
                skipped=len(stale_transient),
                services=stale_transient,
            )

        # Probe persistent backends in parallel
        tasks = [self._probe_one(name) for name in persistent]
        await asyncio.gather(*tasks)

        # Auto-remove chronically dead backends
        to_remove = [
            name
            for name, s in self._status.items()
            if not s.alive and s.consecutive_failures >= self._max_failures
        ]
        if to_remove:
            unregister = getattr(registry, "unregister_service", None)
            if unregister:
                for name in to_remove:
                    logger.warning(
                        "heartbeat_auto_remove",
                        service=name,
                        failures=self._status[name].consecutive_failures,
                    )
                    try:
                        await unregister(name)
                    except Exception as e:  # defensive fallback
                        logger.error(
                            "heartbeat_remove_failed", service=name, error=str(e)
                        )
                    del self._status[name]

        alive = sum(1 for s in self._status.values() if s.alive)
        dead = len(self._status) - alive
        if dead > 0:
            logger.warning(
                "heartbeat_report", alive=alive, dead=dead, total=len(self._status)
            )
        else:
            logger.debug("heartbeat_report", alive=alive, total=len(self._status))
