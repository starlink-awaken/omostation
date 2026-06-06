"""Idle timeout management for MCP proxy connections.

Tracks last-used timestamps per service and periodically sweeps
idle connections, triggering disconnect for services that have
exceeded their configured timeout.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class IdleTimeoutConfig:
    """Configuration for the idle timeout manager.

    Attributes:
        default_timeout: Default idle timeout in seconds (default 300 = 5 min).
        sweep_interval: Interval between idle sweeps in seconds (default 60).
        per_service_timeout: Per-service timeout overrides (service_name → seconds).
    """

    default_timeout: float = 300.0
    sweep_interval: float = 60.0
    per_service_timeout: dict[str, float] = field(default_factory=dict)

    def get_timeout(self, service_name: str) -> float:
        """Return the effective timeout for a given service."""
        return self.per_service_timeout.get(service_name, self.default_timeout)


class IdleTimeoutManager:
    """Manages idle timeout for MCP proxy connections.

    Tracks the last-used timestamp per service and periodically
    invokes a configurable sweep callback to disconnect idle services.

    Usage::

        manager = IdleTimeoutManager(
            registry,
            config=IdleTimeoutConfig(default_timeout=300.0),
            on_idle=lambda name: registry.unregister_service(name),
        )
        manager.start()
        # ... on each successful dispatch:
        manager.refresh("kos")
        # ... on shutdown:
        await manager.stop()
    """

    def __init__(
        self,
        config: IdleTimeoutConfig | None = None,
        on_idle: Any | None = None,
    ):
        """Initialize the idle timeout manager.

        Args:
            config: Idle timeout configuration.
            on_idle: Async callback ``(service_name: str) -> Awaitable[None]``
                     invoked for each service that has timed out.  Typically
                     ``registry.unregister_service()``.
        """
        self._config = config or IdleTimeoutConfig()
        self._last_used: dict[str, float] = {}
        self._on_idle = on_idle
        self._sweep_task: asyncio.Task | None = None
        self._stop_event = asyncio.Event()

    # ── Public API ─────────────────────────────────────────────────

    @property
    def config(self) -> IdleTimeoutConfig:
        return self._config

    @property
    def last_used(self) -> dict[str, float]:
        """Return a copy of the last-used timestamps dict."""
        return dict(self._last_used)

    def refresh(self, service_name: str):
        """Refresh the idle timer for a service.

        Called after every successful tool dispatch to mark the
        service as recently used.
        """
        self._last_used[service_name] = time.monotonic()

    def mark_unloaded(self, service_name: str):
        """Remove tracking for a service that has been explicitly unloaded."""
        self._last_used.pop(service_name, None)

    def start(self):
        """Start the background sweep loop.

        Safe to call multiple times — subsequent calls are no-ops
        if the sweep task is already running.
        """
        if self._sweep_task is not None and not self._sweep_task.done():
            return  # already running
        self._stop_event.clear()
        self._sweep_task = asyncio.create_task(self._sweep_loop())
        logger.info(
            "idle_timeout_started",
            default_timeout=self._config.default_timeout,
            sweep_interval=self._config.sweep_interval,
        )

    async def stop(self):
        """Stop the background sweep loop and wait for it to finish."""
        if self._sweep_task is None:
            return
        self._stop_event.set()
        try:
            await asyncio.wait_for(self._sweep_task, timeout=5.0)
        except (TimeoutError, asyncio.CancelledError):
            self._sweep_task.cancel()
            try:
                await self._sweep_task
            except asyncio.CancelledError:
                pass
        self._sweep_task = None
        self._last_used.clear()
        logger.info("idle_timeout_stopped")

    def idle_services(self, now: float | None = None) -> list[str]:
        """Return list of service names that have exceeded their idle timeout.

        This is a read-only check — does not invoke the idle callback.
        """
        current = time.monotonic() if now is None else now
        idle: list[str] = []
        for svc_name, last_used in list(self._last_used.items()):
            timeout = self._config.get_timeout(svc_name)
            if current - last_used > timeout:
                idle.append(svc_name)
        return sorted(idle)

    # ── Internal ───────────────────────────────────────────────────

    async def _sweep_loop(self):
        """Periodically check for and disconnect idle services."""
        try:
            while not self._stop_event.is_set():
                try:
                    await asyncio.wait_for(
                        self._stop_event.wait(),
                        timeout=self._config.sweep_interval,
                    )
                    # Stop event was set — exit immediately
                    break
                except TimeoutError:
                    pass  # normal: sweep interval elapsed

                await self._sweep_once()
        except asyncio.CancelledError:
            pass
        finally:
            logger.debug("idle_timeout_sweep_ended")

    async def _sweep_once(self, now: float | None = None):
        """Perform a single sweep iteration.

        Args:
            now: Optional monotonic timestamp override (for testing).
                  Uses ``time.monotonic()`` when not provided.
        """
        if not self._on_idle:
            return

        current = time.monotonic() if now is None else now
        idle = self.idle_services(current)
        if not idle:
            return

        logger.info("idle_timeout_sweeping", idle_count=len(idle), services=idle)
        for svc_name in idle:
            self._last_used.pop(svc_name, None)
            try:
                await self._on_idle(svc_name)
            except Exception as e:
                logger.error(
                    "idle_timeout_callback_failed",
                    service=svc_name,
                    error=str(e),
                )
