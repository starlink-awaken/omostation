from __future__ import annotations

"""
---
Type: Module
Status: ACTIVE
Layer: L3
Authority: nucleus/Z-Core/L0-Genome/R0-ACT-SYS-AX01-10_holographic_metadata_axiom.md
---
"""
# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Api Routing Mixin ≡ API
# 内涵 ≝ {Api, Routing, Mixin}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, ApiRoutingMixin)}
# 功能 ⊢ {Api_Routing, Routing_Mixin, Mixin_Init}
# =============================================================================

import contextvars  # noqa: E402
import json  # noqa: E402
import logging  # noqa: E402
import time as _time_module  # noqa: E402
from collections.abc import Awaitable, Callable, Set  # noqa: E402
from typing import Any, Protocol, cast  # noqa: E402

from aiohttp import web  # pyright: ignore[reportMissingImports]  # noqa: E402

# Tracing module is optional; if unavailable, tracing functions are no-ops.
_Tracing = cast(Any, None)
_clear_trace_impl = None
_start_trace_impl = None
_TRACING_AVAILABLE = False
_tc_var: contextvars.ContextVar[Any] = contextvars.ContextVar(
    "trace_context", default=None
)

from .api_types import APIRequest, APIResponse, APIRoute  # noqa: E402
from .auth_models import AuthenticationError  # noqa: E402
from .interfaces import IOAuth2Server, IRateLimiter  # noqa: E402

_log = logging.getLogger(__name__)
_tracing_available = _TRACING_AVAILABLE
TraceContext = cast(Any, _Tracing)

RATE_LIMIT_RETRY_AFTER: int = 60


def start_trace(name: str = "root") -> Any | None:
    """Start tracing when the optional tracing module is available."""
    if _start_trace_impl is None:
        return None
    return _start_trace_impl(name=name)


def clear_trace() -> None:
    """Clear tracing context when the optional tracing module is available."""
    if _clear_trace_impl is None:
        return None
    _clear_trace_impl()


class _AuthenticatedUserLike(Protocol):
    scopes: Set[str]


class _GatewayRoutingSelf(Protocol):
    _routes: dict[str, APIRoute]
    _app: web.Application
    _oauth2_server: IOAuth2Server
    _rate_limiter: IRateLimiter

    def _create_handler(
        self, route: APIRoute
    ) -> Callable[[web.Request], Awaitable[web.StreamResponse]]: ...
    def _inc(self, key: str, amount: int = 1) -> None: ...
    def _record_latency(self, latency_ms: float) -> None: ...
    def _extract_token(self, request: web.Request) -> str | None: ...
    def _get_cors_headers(self) -> dict[str, str]: ...


class _APIRoutingMixin:
    """Route registration and middleware extracted from APIGateway.

    Provides: register_route, _create_handler, _setup_middleware, _find_route.
    Mixed into APIGateway.
    """

    def register_route(self: _GatewayRoutingSelf, route: APIRoute) -> None:
        """
        注册 API 路由

        Args:
            route: API 路由对象
        """
        self._routes[route.path] = route

        # 为 aiohttp 注册路由处理器
        for method in route.methods:
            self._app.router.add_route(
                method.value, route.path, self._create_handler(route)
            )

    def _create_handler(
        self: _GatewayRoutingSelf, route: APIRoute
    ) -> Callable[[web.Request], Awaitable[web.StreamResponse]]:
        """创建 aiohttp 处理器"""

        async def handler(request: web.Request) -> web.Response:
            _t0 = _time_module.monotonic()
            self._inc("requests_total")
            # 1. 限流检查
            if route.rate_limit:
                client_ip = request.remote or "unknown"
                allowed = self._rate_limiter.is_allowed(
                    client_ip=client_ip, route_path=route.path, config=route.rate_limit
                )

                if not allowed:
                    self._inc("requests_rate_limited")
                    self._record_latency((_time_module.monotonic() - _t0) * 1000)
                    resp = APIResponse.error(
                        "Too Many Requests", status_code=429, code="rate_limit_exceeded"
                    ).to_aiohttp_response()
                    resp.headers["Retry-After"] = str(RATE_LIMIT_RETRY_AFTER)
                    return resp

            # 2. 认证检查
            if route.auth_required:
                token = self._extract_token(request)
                if not token:
                    self._inc("requests_unauthorized")
                    self._record_latency((_time_module.monotonic() - _t0) * 1000)
                    return APIResponse.error(
                        "Unauthorized",
                        status_code=401,
                        code="missing_token",
                        details={"message": "Missing authentication token"},
                    ).to_aiohttp_response()

                try:
                    user = cast(
                        _AuthenticatedUserLike,
                        self._oauth2_server.validate_token(token),
                    )
                    request["user"] = user
                    self._inc("auth_token_validated")

                    # 3. 范围检查
                    if route.scopes and not route.scopes.issubset(user.scopes):
                        self._inc("requests_forbidden")
                        self._record_latency((_time_module.monotonic() - _t0) * 1000)
                        return APIResponse.error(
                            "Forbidden",
                            status_code=403,
                            code="insufficient_scope",
                            details={"message": "Insufficient scope"},
                        ).to_aiohttp_response()

                except AuthenticationError as e:
                    self._inc("auth_token_invalid")
                    self._inc("requests_unauthorized")
                    self._record_latency((_time_module.monotonic() - _t0) * 1000)
                    return APIResponse.error(
                        "Unauthorized",
                        status_code=401,
                        code=e.code or "authentication_failed",
                        details={"message": str(e)},
                    ).to_aiohttp_response()

            # 4. 提取路径参数
            path_params = route.match(request.path) or {}
            request["path_params"] = path_params

            # 5. 解析请求体
            body = None
            if request.method in ["POST", "PUT", "PATCH"]:
                try:
                    body = await request.json()
                except json.JSONDecodeError:
                    try:
                        text = await request.text()
                        body = {"raw": text}
                    except (OSError, UnicodeDecodeError):
                        body = {}

            # 6. 创建 API 请求对象
            api_request = APIRequest.from_aiohttp(request)
            api_request.body = body

            # 7. 调用路由处理器
            try:
                result = await route.handler(api_request)
                self._inc("requests_ok")
                self._record_latency((_time_module.monotonic() - _t0) * 1000)

                # 如果是 APIResponse，直接转换
                if isinstance(result, APIResponse):
                    return result.to_aiohttp_response()

                # 否则包装为标准响应
                return APIResponse.ok(result).to_aiohttp_response()

            except web.HTTPException:
                raise
            except Exception as e:
                self._inc("requests_error")
                self._record_latency((_time_module.monotonic() - _t0) * 1000)
                _log.exception(f"Handler exception: {e}")
                return APIResponse.error(
                    "Internal Server Error",
                    status_code=500,
                    code="internal_error",
                    details={"message": str(e)},
                ).to_aiohttp_response()

        return handler

    def _setup_middleware(self: _GatewayRoutingSelf) -> None:
        """设置中间件"""

        @web.middleware
        async def error_middleware(
            request: web.Request,
            handler: Callable[[web.Request], Awaitable[web.StreamResponse]],
        ) -> web.StreamResponse:
            """错误处理中间件"""
            try:
                return await handler(request)
            except web.HTTPException:
                raise
            except Exception as e:
                _log.exception(f"Unhandled exception in middleware: {e}")
                return APIResponse.error(
                    "Internal Server Error",
                    status_code=500,
                    code="internal_error",
                    details={"message": str(e)},
                ).to_aiohttp_response()

        @web.middleware
        async def cors_middleware(
            request: web.Request,
            handler: Callable[[web.Request], Awaitable[web.StreamResponse]],
        ) -> web.StreamResponse:
            """CORS 中间件"""
            if request.method == "OPTIONS":
                return web.Response(headers=self._get_cors_headers())

            response = await handler(request)
            for key, value in self._get_cors_headers().items():
                response.headers[key] = value

            return response

        @web.middleware
        async def request_logging_middleware(
            request: web.Request,
            handler: Callable[[web.Request], Awaitable[web.StreamResponse]],
        ) -> web.StreamResponse:
            """请求日志中间件 — propagates X-Trace-ID into a TraceContext."""
            start_time = _time_module.monotonic()

            # Distributed tracing: continue an upstream trace or start a new one.
            trace_ctx: Any | None = None
            _trace_owned = False
            if _tracing_available:
                raw_trace_header = request.headers.get("X-Trace-ID")
                if raw_trace_header:
                    trace_context_cls = cast(Any, TraceContext)
                    trace_ctx = trace_context_cls.from_header(raw_trace_header)

                    _tc_var.set(trace_ctx)
                else:
                    trace_ctx = start_trace(name=f"D-Gateway.{request.method}")
                _trace_owned = True
                request["trace_ctx"] = trace_ctx

            try:
                response = await handler(request)
                elapsed = (_time_module.monotonic() - start_time) * 1000  # ms
                _tid = trace_ctx.trace_id[:8] if trace_ctx else ""
                _log.info(
                    f"{request.method} {request.path} - {response.status} - {elapsed:.2f}ms"
                    + (f" trace={_tid}" if _tid else "")
                )
                if trace_ctx is not None:
                    response.headers["X-Trace-ID"] = trace_ctx.to_header()
                return response
            except Exception:
                _log.exception(f"Request failed: {request.method} {request.path}")
                raise
            finally:
                if _trace_owned and _tracing_available:
                    clear_trace()

        @web.middleware
        async def version_middleware(
            request: web.Request,
            handler: Callable[[web.Request], Awaitable[web.StreamResponse]],
        ) -> web.StreamResponse:
            """Inject API version and module identity headers on every response."""
            response = await handler(request)
            response.headers["X-BOS-API-Version"] = "1.0"
            response.headers["X-BOS-Module"] = "D-Gateway"
            return response

        self._app.middlewares.extend(
            [
                error_middleware,
                cors_middleware,
                request_logging_middleware,
                version_middleware,
            ]
        )

    def _find_route(
        self: _GatewayRoutingSelf, path: str, method: str
    ) -> APIRoute | None:
        """查找匹配的路由"""
        for route in self._routes.values():
            if method in [m.value for m in route.methods]:
                params = route.match(path)
                if params:
                    return route
        return None
