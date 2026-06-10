from __future__ import annotations

"""
---
Type: Infrastructure
Status: ACTIVE
Version: 2.1.0 (Anti-Storm)
Owner: '@Copilot'
Authority: AGENTS.md
Layer: L3
Summary: 'FederationRouter — Enhanced with Token Bucket and Strict Circuit Breaking for Anti-Storm.'
---
"""
# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Federation Router ≡ Router
# 内涵 ≝ {Federation, Router}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, FederationRouter)}
# 功能 ⊢ {Federation_Router, Init_Federation, Validate_Router}
# =============================================================================

import asyncio  # noqa: E402
import enum  # noqa: E402
import json  # noqa: E402
import logging  # noqa: E402
import threading  # noqa: E402
import time  # noqa: E402
import uuid  # noqa: E402
from dataclasses import dataclass, field  # noqa: E402
from typing import Any, Protocol, runtime_checkable  # noqa: E402

_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Metrics & Trace (Unchanged from 2.0.0)
# ---------------------------------------------------------------------------

try:
    from bos_daemon.main import metrics as _metrics  # type: ignore[import-not-found]
except ImportError:

    class _MetricsFallback:
        def increment(
            self, name: str, value: int = 1, labels: dict | None = None
        ) -> None:
            pass

        def gauge(self, name: str, value: float) -> None:
            pass

    _metrics = _MetricsFallback()


class _RequestTrace:
    __slots__ = ("trace_id", "start_time", "operation", "labels")

    def __init__(self, operation: str, **labels: Any) -> None:
        super().__init__()
        self.trace_id = str(uuid.uuid4())[:8]
        self.start_time = time.monotonic()
        self.operation = operation
        self.labels = labels

    def finish(self, status: str = "ok") -> float:
        elapsed_ms = round((time.monotonic() - self.start_time) * 1000, 2)
        _log.info(
            "[trace:%s] %s status=%s elapsed_ms=%s %s",
            self.trace_id,
            self.operation,
            status,
            elapsed_ms,
            " ".join(f"{k}={v}" for k, v in self.labels.items()),
        )
        return elapsed_ms


# ---------------------------------------------------------------------------
# Anti-Storm: Token Bucket Rate Limiter
# ---------------------------------------------------------------------------


class TokenBucket:
    """线程安全的令牌桶限流器。"""

    def __init__(self, capacity: float, fill_rate: float) -> None:
        self.capacity = capacity
        self.fill_rate = fill_rate
        self.tokens = capacity
        self.last_update = time.monotonic()
        self._lock = threading.Lock()

    def consume(self, amount: float = 1.0) -> bool:
        with self._lock:
            now = time.monotonic()
            # 补充令牌
            self.tokens = min(
                self.capacity, self.tokens + (now - self.last_update) * self.fill_rate
            )
            self.last_update = now
            if self.tokens >= amount:
                self.tokens -= amount
                return True
            return False


# ---------------------------------------------------------------------------
# Anti-Storm: Circuit Breaker State Machine
# ---------------------------------------------------------------------------


class CBState(enum.Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half-open"


@dataclass
class _CircuitBreaker:
    failure_count: int = 0
    open_until: float = 0.0
    FAILURE_THRESHOLD: int = 5
    OPEN_DURATION_S: float = 30.0
    _lock: threading.Lock = field(
        default_factory=threading.Lock, compare=False, repr=False
    )
    _state: CBState = CBState.CLOSED
    _probe_in_flight: bool = False

    def can_execute(self) -> bool:
        with self._lock:
            if self._state == CBState.CLOSED:
                return True
            if self._state == CBState.OPEN:
                if time.monotonic() >= self.open_until:
                    # 冷却期结束，进入 HALF-OPEN 探测
                    self._state = CBState.HALF_OPEN
                    self._probe_in_flight = True
                    return True
                return False
            if self._state == CBState.HALF_OPEN:
                # 已经有一个探测在飞，其他拦截
                return False
            return False

    def record_success(self) -> None:
        with self._lock:
            self.failure_count = 0
            self.open_until = 0.0
            self._state = CBState.CLOSED
            self._probe_in_flight = False

    def record_failure(self) -> None:
        with self._lock:
            self.failure_count += 1
            if (
                self.failure_count >= self.FAILURE_THRESHOLD
                or self._state == CBState.HALF_OPEN
            ):
                self.open_until = time.monotonic() + self.OPEN_DURATION_S
                self._state = CBState.OPEN
                self._probe_in_flight = False
                _log.warning(
                    "Circuit breaker OPEN for %s seconds", self.OPEN_DURATION_S
                )


# ---------------------------------------------------------------------------
# FederationRouter
# ---------------------------------------------------------------------------


@dataclass
class NodeRecord:
    node_id: str
    endpoint: str
    capabilities: list[str] = field(default_factory=list)
    registered_at: float = field(default_factory=time.time)


@dataclass
class RemoteNode:
    """Lightweight representation of a remote federation peer."""

    node_id: str
    endpoint: str
    online: bool = True
    latency_ms: float = 50.0


@dataclass
class RoutingDecision:
    """Outcome of a federation routing evaluation."""

    local: bool
    target_node: RemoteNode | NodeRecord | None
    reason: str
    estimated_latency_ms: float = 0.0


@runtime_checkable
class AsyncHTTPClient(Protocol):
    async def post(self, url: str, json: dict, timeout: float) -> Any: ...
    async def get(self, url: str, timeout: float) -> Any: ...


class FederationRouter:
    def __init__(
        self,
        http_client: AsyncHTTPClient | None = None,
        timeout_s: float = 10.0,
        max_retries: int = 3,
    ) -> None:
        self._nodes: dict[str, NodeRecord] = {}
        self._breakers: dict[str, _CircuitBreaker] = {}
        # 全局限流器 (默认 100 QPS)
        self._limiter = TokenBucket(capacity=100, fill_rate=50)
        self._http = http_client
        self._timeout = timeout_s
        self._max_retries = max_retries

    def register_node(
        self, node_id: str, endpoint: str, capabilities: list[str] | None = None
    ) -> None:
        from agora.ssrf_guard import validate_external_url

        validate_external_url(endpoint)
        self._nodes[node_id] = NodeRecord(
            node_id=node_id,
            endpoint=endpoint.rstrip("/"),
            capabilities=capabilities or [],
        )
        if node_id not in self._breakers:
            self._breakers[node_id] = _CircuitBreaker()

    def unregister_node(self, node_id: str) -> bool:
        """Remove a previously registered node. Returns True if found."""
        removed = self._nodes.pop(node_id, None) is not None
        self._breakers.pop(node_id, None)
        return removed

    def list_nodes(self) -> list[NodeRecord]:
        """Return a snapshot of all registered nodes."""
        return list(self._nodes.values())

    async def health_check(self, node_id: str) -> bool:
        """Probe a registered node's health endpoint. Returns False on any error."""
        record = self._nodes.get(node_id)
        if record is None:
            return False
        try:
            if self._http is not None:
                resp = await self._http.get(
                    f"{record.endpoint}/health", timeout=self._timeout
                )
                # Support both httpx-style (.status_code) and stdlib-style (.status)
                for attr in ("status_code", "status"):
                    code = getattr(resp, attr, None)
                    if isinstance(code, int):
                        return code == 200
                # Mock/unknown client — treat non-exception as success
                return True
            # stdlib fallback
            import urllib.request

            req = urllib.request.Request(f"{record.endpoint}/health", method="GET")  # noqa: S310
            with urllib.request.urlopen(req, timeout=self._timeout) as r:  # noqa: S310
                return r.status == 200
        except Exception:
            breaker = self._breakers.get(node_id)
            if breaker:
                breaker.record_failure()
            return False

    def router_health_check(self) -> dict[str, Any]:
        """Detailed health status across all registered nodes and breakers."""
        cb_states: dict[str, str] = {}
        degraded = False
        for nid, breaker in self._breakers.items():
            # Determine effective state from both _state and open_until
            if breaker.open_until > 0 and breaker.open_until > time.monotonic():
                cb_states[nid] = "open"
                degraded = True
            elif breaker.open_until > 0 and breaker.open_until <= time.monotonic():
                cb_states[nid] = "half-open"
            elif breaker._state == CBState.OPEN:
                cb_states[nid] = "open"
                degraded = True
            elif breaker._state == CBState.HALF_OPEN:
                cb_states[nid] = "half-open"
            else:
                cb_states[nid] = "closed"

        status = "degraded" if degraded else "healthy"
        redis_available: bool | None = None
        mq = getattr(self, "_message_queue", None)
        if mq is not None:
            redis_available = getattr(mq, "is_available", False)

        return {
            "status": status,
            "nodes_registered": len(self._nodes),
            "circuit_breakers": cb_states,
            "redis_available": redis_available,
        }

    def route(self, uri: Any) -> RoutingDecision:
        """Evaluate routing for a parsed BOS-URI. Returns a RoutingDecision."""
        node_id = getattr(uri, "node_id", None)
        if node_id is None:
            return RoutingDecision(
                local=True, target_node=None, reason="local_preferred"
            )

        record = self._nodes.get(node_id)
        if record is None:
            return RoutingDecision(
                local=True, target_node=None, reason="local_fallback"
            )

        cb = self._breakers.get(node_id)
        if cb and not cb.can_execute():
            return RoutingDecision(
                local=True, target_node=None, reason="local_fallback"
            )

        remote = RemoteNode(
            node_id=record.node_id, endpoint=record.endpoint, online=True
        )
        return RoutingDecision(
            local=False,
            target_node=remote,
            reason="remote_capable",
            estimated_latency_ms=remote.latency_ms,
        )

    async def execute_remote(
        self,
        node: RemoteNode,
        uri: Any,
        payload: dict[str, object],
    ) -> dict[str, object]:
        """Forward execution to a remote node with one retry."""
        url = f"{node.endpoint}/synapse/execute"
        # Merge URI context into request body
        request_body = dict(payload)
        for attr in ("domain", "resource", "action"):
            val = getattr(uri, attr, None)
            if val is not None:
                request_body[attr] = val
        last_exc: Exception | None = None
        for attempt in range(2):
            try:
                if self._http is not None:
                    resp = await self._http.post(
                        url, json=request_body, timeout=self._timeout
                    )
                    return resp.json() if hasattr(resp, "json") else resp
                return {"status": "error", "error": "no http client"}
            except (TimeoutError, OSError, ConnectionError) as exc:
                last_exc = exc
                if attempt == 0:
                    await asyncio.sleep(0.1)
        return {"status": "error", "error": str(last_exc), "node_id": node.node_id}

    async def route_to_node(self, node_id: str, envelope: Any) -> dict[str, Any]:
        trace = _RequestTrace("route_to_node", node_id=node_id)

        # 1. 限流保护
        if not self._limiter.consume():
            _log.warning("Anti-Storm: Rate limit exceeded for outgoing requests")
            _metrics.increment("gateway.errors_total", labels={"type": "rate_limit"})
            return {"status": "error", "error": "429: Too Many Requests (Anti-Storm)"}

        record = self._nodes.get(node_id)
        if record is None:
            _metrics.increment("gateway.errors_total", labels={"type": "unknown_node"})
            return {"status": "error", "error": f"Unknown node: {node_id}"}

        # 2. 熔断保护
        cb = self._breakers[node_id]
        if not cb.can_execute():
            _metrics.increment("gateway.errors_total", labels={"type": "circuit_open"})
            return {
                "status": "error",
                "error": f"Circuit breaker OPEN for node {node_id}",
            }

        url = f"{record.endpoint}/synapse/accept"
        payload = self._serialise(envelope)

        last_exc = None
        for attempt in range(self._max_retries):  # 默认 3 次尝试
            try:
                response = await self._post(url, payload)
                cb.record_success()
                _metrics.increment("gateway.messages_routed")
                trace.finish("ok")
                return response
            except (TimeoutError, OSError, ConnectionError) as exc:
                last_exc = exc
                cb.record_failure()
                if attempt < self._max_retries - 1:  # 如果还有重试机会
                    wait_s = (2**attempt) + 0.1
                    _log.debug(
                        f"Retrying federation route to {node_id} in {wait_s}s (attempt {attempt + 1})"
                    )
                    await asyncio.sleep(wait_s)

        _metrics.increment(
            "gateway.errors_total", labels={"type": "federation_exhausted"}
        )
        trace.finish("error")
        return {"status": "error", "error": f"Max retries exceeded: {last_exc}"}

    @staticmethod
    def _serialise(envelope: Any) -> dict[str, object]:
        if hasattr(envelope, "__dict__"):
            return {k: v for k, v in envelope.__dict__.items() if not k.startswith("_")}
        if isinstance(envelope, dict):
            return envelope
        if isinstance(envelope, (str, int, float, bool, list)):
            return {"value": envelope}
        raise TypeError(f"cannot serialise {type(envelope).__name__}")

    async def _post(self, url: str, payload: dict, method: str = "POST") -> dict:
        if self._http is not None:
            if method == "GET":
                resp = await self._http.get(url, timeout=self._timeout)
            else:
                resp = await self._http.post(url, json=payload, timeout=self._timeout)
            return resp.json() if hasattr(resp, "json") else resp

        from concurrent.futures import ThreadPoolExecutor

        loop = asyncio.get_running_loop()
        with ThreadPoolExecutor(max_workers=1) as executor:
            return await loop.run_in_executor(
                executor, self._urllib_post, url, payload, method
            )

    def _urllib_post(self, url: str, payload: dict, method: str) -> dict:
        import urllib.request

        data = json.dumps(payload).encode() if method == "POST" else None
        req = urllib.request.Request(  # noqa: S310
            url, data=data, headers={"Content-Type": "application/json"}, method=method
        )
        with urllib.request.urlopen(req, timeout=self._timeout) as resp:  # noqa: S310
            return json.loads(resp.read().decode("utf-8"))
