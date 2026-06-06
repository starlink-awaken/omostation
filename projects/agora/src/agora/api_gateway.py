"""
---
Type: Module
Status: ACTIVE
Version: 1.0.0
Authority: organs/D-Gateway/AGENTS.md
Layer: L3
---
"""

from __future__ import annotations

# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Api Gateway ≡ API
# 内涵 ≝ {Api, Gateway}
# 外延 ≝ {e | e ∈ D-Gateway ∧ implements(e, ApiGateway)}
# 功能 ⊢ {Api_Gateway, Init_Api, Validate_Gateway}
# =============================================================================

"""
---
Type: organ
Status: active
Layer: D-Gateway
Summary: API gateway providing HTTP routing, OAuth2 auth, rate limiting, and webhook handling.
Owner: SharedBrain
Version: 1.0.0
Authority: nucleus/Z-Spore/dna/organ-contract-v1.md
---

Security Architecture
---------------------
Authentication flows through two paths:

1. **OAuth2 Bearer JWT** — for external / user-facing endpoints.
   Tokens are issued by ``OAuth2Server`` and validated on each request.
   The JWT signing key is read exclusively from the ``SECRET_KEY`` env var;
   the server raises ``ValueError`` at startup if it is absent.

2. **Cluster Key (HMAC)** — for internal node-to-node endpoints
   (``/api/v1/tasks/dispatch``, ``/api/v1/memory/fact_graph``).
   The shared secret is read from ``BOS_CLUSTER_KEY``.  All comparisons use
   ``hmac.compare_digest`` to prevent timing-based side-channel attacks.
   The module raises ``ValueError`` if ``BOS_CLUSTER_KEY`` is not set.

Path parameters are validated against the allowlist pattern
``^[A-Za-z0-9_\\-./]+$`` via ``_sanitize_path_param()`` before use.
"""
import asyncio
import logging
import os
import re
import threading
import time as _time_module
from collections import deque
from typing import Any, cast

_log = logging.getLogger(__name__)
logger = logging.getLogger(__name__)

# Configure structured log format once at module level (no-op if already configured)
logging.basicConfig(
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
    level=logging.INFO,
)

from aiohttp import web  # pyright: ignore[reportMissingImports]

from .interfaces import IOAuth2Server, IRateLimiter  # Protocol checks

_Tracing = cast(Any, None)
_clear_trace_impl = None
_get_current_trace_impl = None
_start_trace_impl = None
_TRACING_AVAILABLE = False

TraceContext = cast(Any, _Tracing)

def get_current_trace() -> Any | None:
    if _get_current_trace_impl is None:
        return None
    return _get_current_trace_impl()

def start_trace(name: str = "root") -> Any | None:
    if _start_trace_impl is None:
        return None
    return _start_trace_impl(name=name)

def clear_trace() -> None:
    if _clear_trace_impl is None:
        return None
    _clear_trace_impl()

# =============================================================================
# Constants
# =============================================================================

#: Default listen host for the API gateway.
DEFAULT_HOST: str = "0.0.0.0"  # noqa: S104

#: Default listen port for the API gateway.
DEFAULT_PORT: int = 8080

#: Cluster key env-var name used for node-to-node auth.
ENV_CLUSTER_KEY: str = "BOS_CLUSTER_KEY"

#: Sentinel used in tests to bypass the env-var enforcement.
#: Set ``BOS_CLUSTER_KEY`` to this value ONLY in unit tests — never in production.
_TEST_CLUSTER_KEY_SENTINEL: str = "__TEST_ONLY__"

#: Maximum concurrent in-flight requests (bulkhead limit).
MAX_CONCURRENT_REQUESTS: int = 200

#: Sliding window size for latency percentile tracking.
LATENCY_WINDOW_SIZE: int = 1000

#: Default Retry-After seconds for 429 rate-limit responses.
RATE_LIMIT_RETRY_AFTER: int = 60

# _DEFAULT_CLUSTER_KEY intentionally removed — hard-coded fallback secrets
# are a security anti-pattern.  Use _get_cluster_key() instead.

def _get_cluster_key() -> str:
    """Return the cluster key from the environment.

    Raises:
        ValueError: If ``BOS_CLUSTER_KEY`` is not set, to prevent silent use
            of a hard-coded fallback in production.
    """
    key = os.environ.get(ENV_CLUSTER_KEY)
    if not key:
        raise ValueError(
            f"Environment variable '{ENV_CLUSTER_KEY}' is required but not set. "
            "Set it to a strong random secret before starting the gateway."
        )
    return key

# Path-parameter allowlist pattern — blocks path-traversal and injection chars.
_PATH_PARAM_RE = re.compile(r"^[A-Za-z0-9_\-./]+$")

def _sanitize_path_param(value: str) -> str:
    """Validate and return a path parameter value against the allowlist pattern.

    Only characters matching ``^[A-Za-z0-9_\\-./]+$`` are accepted.  This
    prevents path-traversal (``../``), null-byte injection, shell metachar
    injection, and similar attacks.

    Args:
        value: The raw path parameter value extracted from the request.

    Returns:
        The original *value* unchanged if it passes validation.

    Raises:
        ValueError: If *value* contains characters outside the allowlist.
    """
    if not _PATH_PARAM_RE.match(value):
        raise ValueError(
            f"Path parameter contains forbidden characters: {value!r}. Only [A-Za-z0-9_\\-./] are allowed."
        )
    return value

def _supports_oauth2_server(candidate: Any) -> bool:
    """Best-effort structural check used only for runtime warnings."""
    return all(callable(getattr(candidate, attr, None)) for attr in ("validate_token", "issue_token", "list_clients"))

def _supports_rate_limiter(candidate: Any) -> bool:
    """Best-effort structural check used only for runtime warnings."""
    return callable(getattr(candidate, "is_allowed", None))

from .api_docs_mixin import _APIDocsMixin  # type: ignore[import-not-found]
from .api_handlers_mixin import _APIHandlersMixin
from .api_routing_mixin import _APIRoutingMixin
from .api_types import APIRequest, APIResponse, APIRoute, HTTPMethod  # noqa: F401


class APIGateway(_APIRoutingMixin, _APIHandlersMixin, _APIDocsMixin):
    """
    RESTful API 网关

    功能:
    1. 路由管理 - 动态路由注册和匹配
    2. 认证授权 - OAuth2/JWT 验证
    3. 限流控制 - 令牌桶限流
    4. 请求验证 - Schema 验证
    5. 响应缓存 - Redis 缓存
    6. 错误处理 - 统一错误响应
    7. CORS - 跨域资源共享
    """

    def __init__(
        self,
        oauth2_server: IOAuth2Server,
        rate_limiter: IRateLimiter,
        cors_origins: list[str] | None = None,
        enable_trailing_slash: bool = True,
    ) -> None:
        """
        初始化 API 网关

        Args:
            oauth2_server: OAuth2 服务器实例
            rate_limiter: 限流器实例
            cors_origins: 允许的 CORS 源列表
            enable_trailing_slash: 是否启用尾随斜杠重定向
        """
        self.status = "active"
        self._oauth2_server = oauth2_server
        self._rate_limiter = rate_limiter
        # Soft Protocol conformance checks — warn rather than hard-fail for
        # backward compatibility, but surface structural mismatches early.
        import warnings

        if oauth2_server is not None and not _supports_oauth2_server(oauth2_server):
            warnings.warn(
                f"oauth2_server ({type(oauth2_server).__name__}) does not satisfy "
                "IOAuth2Server protocol; expected validate_token/issue_token/list_clients",
                stacklevel=2,
            )
        if rate_limiter is not None and not _supports_rate_limiter(rate_limiter):
            warnings.warn(
                f"rate_limiter ({type(rate_limiter).__name__}) does not satisfy "
                "IRateLimiter protocol; expected is_allowed(client_ip, route_path, config)",
                stacklevel=2,
            )
        self._routes: dict[str, APIRoute] = {}
        self._cors_origins = cors_origins or ["*"]
        self._enable_trailing_slash = enable_trailing_slash
        self._app = web.Application()
        self._start_time: float = _time_module.monotonic()
        # Observability counters — structured metrics for monitoring.
        # Thread-safety: all mutations go through _inc() which acquires
        # _metrics_lock before modifying the dict.  Reads (e.g. health_check)
        # take a snapshot under the same lock so callers always see a
        # consistent, point-in-time view of the counters.
        self._metrics_lock = threading.Lock()
        self.metrics: dict[str, int] = {
            "requests_total": 0,
            "requests_ok": 0,
            "requests_error": 0,
            "requests_rate_limited": 0,
            "requests_unauthorized": 0,
            "requests_forbidden": 0,
            "auth_token_validated": 0,
            "auth_token_invalid": 0,
        }
        # Sliding window of the last 1 000 response-time samples (milliseconds).
        # Used to compute p50 / p95 latency percentiles in health_check().
        self._latency_window: deque[float] = deque(maxlen=LATENCY_WINDOW_SIZE)
        self._shutting_down: bool = False
        # Bulkhead: cap concurrent in-flight requests to prevent thread exhaustion.
        self._max_concurrent: int = MAX_CONCURRENT_REQUESTS
        self._semaphore = asyncio.Semaphore(self._max_concurrent)
        self._setup_middleware()
        # 注册核心系统路由
        self.register_route(
            APIRoute(
                path="/api/v1/handshake",
                methods=[HTTPMethod.POST],
                handler=self.handshake_handler,
                auth_required=False,  # 握手自备 Cluster Key 校验
                description="Soul Handshake for P2P nodes",
            )
        )

        self.register_route(
            APIRoute(
                path="/api/v1/tasks/dispatch",
                methods=[HTTPMethod.POST],
                handler=self.task_dispatch_handler,
                auth_required=False,
                description="Receive dispatched tasks from remote nodes",
            )
        )

        self.register_route(
            APIRoute(
                path="/api/v1/memory/fact_graph",
                methods=[HTTPMethod.GET],
                handler=self.fact_graph_query_handler,
                auth_required=False,
                description="Federated FactGraph Query",
            )
        )
        self.register_route(
            APIRoute(
                path="/api/v1/swarm/nodes",
                methods=[HTTPMethod.GET],
                handler=self.swarm_nodes_handler,
                auth_required=False,
                description="Get list of active P2P swarm nodes",
            )
        )
        # Register built-in observability endpoints directly on the aiohttp
        # router (not through APIRoute) so they are available without auth.
        self._app.router.add_get("/metrics", self._metrics_handler)
        self._app.router.add_get("/health", self._health_handler)

    # ------------------------------------------------------------------
    # Thread-safe metric helpers
    # ------------------------------------------------------------------

    def _inc(self, key: str, amount: int = 1) -> None:
        """Increment a metrics counter atomically under _metrics_lock."""
        with self._metrics_lock:
            self.metrics[key] = self.metrics.get(key, 0) + amount

    def _record_latency(self, latency_ms: float) -> None:
        """Append a response-time sample (ms) to the sliding window."""
        with self._metrics_lock:
            self._latency_window.append(latency_ms)

    def _percentile(self, p: float) -> float:
        """Return the p-th percentile (0–100) of the latency window, or 0.0."""
        with self._metrics_lock:
            samples = sorted(self._latency_window)
        if not samples:
            return 0.0
        idx = max(0, int(len(samples) * p / 100) - 1)
        return round(samples[idx], 3)

    def _extract_token(self, request: web.Request) -> str | None:
        """从请求头提取令牌"""
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            return auth_header[7:]
        return None

    def _get_cors_headers(self) -> dict[str, str]:
        """获取 CORS 头"""
        return {
            "Access-Control-Allow-Origin": self._cors_origins[0] if len(self._cors_origins) == 1 else "*",
            "Access-Control-Allow-Methods": "GET, POST, PUT, PATCH, DELETE, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Requested-With",
            "Access-Control-Max-Age": "86400",
        }

    async def start(self, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> None:  # pragma: no cover
        """
        Start the API gateway HTTP server.

        Args:
            host: Listen host (default ``0.0.0.0``).
            port: Listen port (default ``8080``).

        Registers SIGTERM and SIGINT handlers so the gateway shuts down
        gracefully when the process receives a termination signal (e.g. from
        ``docker stop`` or Kubernetes).
        """
        import asyncio as _asyncio
        import signal as _signal

        runner = web.AppRunner(self._app)
        await runner.setup()
        # Store the runner so shutdown() can call runner.cleanup()
        self._runner = runner
        site = web.TCPSite(runner, host, port)
        await site.start()
        logger.info("API Gateway started on http://%s:%s", host, port)

        # Install graceful-shutdown signal handlers
        loop = _asyncio.get_event_loop()
        for sig in (_signal.SIGTERM, _signal.SIGINT):
            loop.add_signal_handler(
                sig,
                lambda: _asyncio.create_task(self.shutdown()),
            )

    async def stop(self) -> None:  # pragma: no cover
        """Stop the API gateway."""
        await self._app.shutdown()

    async def shutdown(self) -> None:
        """Gracefully shut down the gateway, draining in-flight requests.

        Sets ``_shutting_down`` to ``True`` so middleware can reject new
        requests, then cleans up the aiohttp runner.  Signal handlers installed
        by :meth:`start` call this method when SIGTERM / SIGINT is received.
        """
        import asyncio as _asyncio

        _log.info("Gateway shutting down — draining connections…")
        self._shutting_down = True
        # Yield control so any in-flight coroutines can complete their current
        # await point before we tear down the runner.
        await _asyncio.sleep(0)
        # Attempt to clean up the runner if it was stored during start().
        runner = getattr(self, "_runner", None)
        if runner is not None:
            try:
                await runner.cleanup()
            except OSError as exc:  # pragma: no cover
                _log.warning("Error during runner cleanup: %s", exc)
        _log.info("Gateway shutdown complete")

    def get_app(self) -> web.Application:
        """Return the underlying aiohttp Application."""
        return self._app

_global_api_gateway: APIGateway | None = None

def get_api_gateway(
    oauth2_server: IOAuth2Server | None = None,
    rate_limiter: IRateLimiter | None = None,
) -> APIGateway:
    """获取全局 API 网关实例"""
    global _global_api_gateway
    if _global_api_gateway is None:
        from .oauth2_server import get_oauth2_server
        from .rate_limiter import get_rate_limiter  # type: ignore[import-not-found]

        _global_api_gateway = APIGateway(
            oauth2_server=cast(IOAuth2Server, oauth2_server or get_oauth2_server()),
            rate_limiter=cast(IRateLimiter, rate_limiter or get_rate_limiter()),
        )
    return _global_api_gateway
