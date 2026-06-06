"""Circuit breaker state machine for service health management."""

from __future__ import annotations

import asyncio
import contextlib
import time
from collections.abc import Callable

from agora.core.service_base import Service, is_safe_url  # type: ignore[import-not-found]


class CircuitBreaker:
    """Circuit breaker attached to a service in the registry.

    Tracks failure counts, cooldown periods, and half-open probing.
    Delegates transition logging and alerting via callbacks.
    """

    def __init__(
        self,
        max_failures: int = 3,
        cooldown: float = 60.0,
        success_threshold: int = 2,
        alert_callback: Callable | None = None,
        alert_webhook: str = "",
    ):
        self._max_failures = max_failures
        self._cooldown = cooldown
        self._success_threshold = success_threshold
        self._alert_callback = alert_callback
        self._alert_webhook = alert_webhook

    # ── Webhook alert ─────────────────────────────────────────────

    def send_webhook_alert(self, name: str, prev: str, new: str, failures: int):
        """Send circuit state change alert via webhook (async fire-and-forget)."""
        if not self._alert_webhook:
            return
        if not is_safe_url(self._alert_webhook):
            import structlog

            logger = structlog.get_logger(__name__)
            logger.warning("webhook_alert_blocked", service=name, webhook=self._alert_webhook)
            return
        import httpx

        async def _send():
            async with httpx.AsyncClient(timeout=5) as c:
                await c.post(
                    self._alert_webhook,
                    json={
                        "service": name,
                        "prev_state": prev,
                        "new_state": new,
                        "failures": failures,
                    },
                )

        try:
            loop = asyncio.get_running_loop()
            loop.create_task(_send())
        except RuntimeError:
            with contextlib.suppress(Exception):
                asyncio.run(_send())

    # ── Service probe helpers ─────────────────────────────────────

    def try_half_open(self, svc: Service) -> bool:
        """Attempt a half-open probe on a service. Returns True if probe should proceed."""
        if not svc.healthy and not svc.half_open and time.monotonic() >= svc.cooldown_until:
            svc.half_open = True
            return True
        return False

    def mark_failure(self, svc: Service, name: str, add_transition: Callable, alert_name: str | None = None):
        """Record a failure and potentially open the circuit."""
        prev_state = svc.circuit_state
        svc.failure_count += 1
        alert_name = alert_name or name

        if svc.half_open:
            svc.healthy = False
            svc.half_open = False
            svc.consecutive_successes = 0
            svc.cooldown_until = time.monotonic() + (self._cooldown * 2)
            add_transition(alert_name, prev_state, "OPEN", "Circuit breaker: half-open probe failed", "health_check")
            self._fire_alert(alert_name, prev_state, "OPEN (HALF_OPEN->OPEN)", svc.failure_count)
        elif svc.failure_count >= self._max_failures:
            svc.cooldown_until = time.monotonic() + self._cooldown
            svc.healthy = False
            new_state = svc.circuit_state
            if prev_state != new_state:
                add_transition(
                    alert_name,
                    prev_state,
                    new_state,
                    f"Circuit breaker opened: {svc.failure_count} failures",
                    "health_check",
                )
            if prev_state != "OPEN":
                self._fire_alert(alert_name, prev_state, "OPEN", svc.failure_count)

    def mark_success(self, svc: Service, name: str, add_transition: Callable):
        """Record a success and potentially close the circuit."""
        prev_state = svc.circuit_state
        if svc.half_open:
            svc.consecutive_successes += 1
            if svc.consecutive_successes >= self._success_threshold:
                svc.failure_count = 0
                svc.healthy = True
                svc.half_open = False
                svc.consecutive_successes = 0
                svc.cooldown_until = 0.0
                add_transition(name, prev_state, "CLOSED", "Circuit breaker recovered", "health_check")
        else:
            svc.failure_count = max(0, svc.failure_count - 1)
            if svc.failure_count < self._max_failures and not svc.healthy:
                svc.healthy = True
                svc.cooldown_until = 0.0
                new_state = svc.circuit_state
                if prev_state != new_state:
                    add_transition(name, prev_state, new_state, "Service recovered after degradation", "health_check")

    def get_status(self, svc: Service, name: str) -> dict:
        """Get detailed circuit breaker status for a service."""
        return {
            "name": name,
            "state": svc.circuit_state,
            "healthy": svc.healthy,
            "failure_count": svc.failure_count,
            "cooldown_remaining": max(0, svc.cooldown_until - time.monotonic()) if not svc.healthy else 0,
        }

    def _fire_alert(self, name: str, prev: str, new: str, failures: int):
        """Fire alert callback and webhook for a state change."""
        if self._alert_callback:
            self._alert_callback(name, prev, new, failures)
        self.send_webhook_alert(name, prev, new, failures)
