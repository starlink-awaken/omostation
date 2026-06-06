"""API route, request, and response types.

Extracted from SharedBrain D_Gateway.  Uses agora's own RateLimitConfig
and auth models instead of nucleus imports.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from aiohttp import web

from agora.auth.auth_models import AuthenticatedUser  # type: ignore[import-not-found]
from agora.rate_limit import RateLimitConfig  # type: ignore[import-not-found]


class HTTPMethod(Enum):
    """HTTP 方法"""

    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"
    OPTIONS = "OPTIONS"
    HEAD = "HEAD"


@dataclass
class APIRoute:
    """
    API 路由定义

    Attributes:
        path: 路由路径 (支持参数：/api/users/{user_id})
        methods: 允许的 HTTP 方法
        handler: 处理函数
        auth_required: 是否需要认证
        scopes: 需要的授权范围
        rate_limit: 限流配置
        tags: 路由标签 (用于文档)
        description: 路由描述
    """

    path: str
    methods: list[HTTPMethod]
    handler: Callable
    auth_required: bool = True
    scopes: set[str] = field(default_factory=set)
    rate_limit: RateLimitConfig | None = None
    tags: list[str] = field(default_factory=list)
    description: str = ""

    def __post_init__(self) -> None:
        # 编译路径正则表达式
        self._path_pattern = re.sub(r"\{(\w+)\}", r"(?P<\1>[^/]+)", self.path)
        self._compiled_pattern = re.compile(f"^{self._path_pattern}$")

    def match(self, path: str) -> dict[str, str] | None:
        """
        匹配路径

        Args:
            path: 请求路径

        Returns:
            路径参数匹配结果，不匹配返回 None
        """
        match = self._compiled_pattern.match(path)
        if match:
            return match.groupdict()
        return None


@dataclass
class APIRequest:
    """
    API 请求定义

    Attributes:
        method: HTTP 方法
        path: 请求路径
        headers: 请求头
        query_params: 查询参数
        body: 请求体
        client_ip: 客户端 IP
        authenticated_user: 认证用户
        path_params: 路径参数
    """

    method: HTTPMethod
    path: str
    headers: dict[str, str]
    query_params: dict[str, str] = field(default_factory=dict)
    body: dict | None = None
    client_ip: str = ""
    authenticated_user: AuthenticatedUser | None = None
    path_params: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_aiohttp(cls, request: web.Request) -> APIRequest:
        """从 aiohttp 请求创建"""
        return cls(
            method=HTTPMethod[request.method],
            path=request.path,
            headers=dict(request.headers),
            query_params=dict(request.query),
            client_ip=request.remote or "",
            authenticated_user=request.get("user"),
            path_params=request.get("path_params", {}),
        )


@dataclass
class APIResponse:
    """
    API 响应定义

    Attributes:
        status_code: HTTP 状态码
        body: 响应体
        headers: 响应头
    """

    status_code: int
    body: Any
    headers: dict[str, str] = field(default_factory=dict)

    @classmethod
    def ok(cls, data: Any, status_code: int = 200, message: str = "OK") -> APIResponse:
        """成功响应"""
        return cls(status_code=status_code, body={"success": True, "message": message, "data": data})

    @classmethod
    def error(
        cls,
        message: str,
        status_code: int = 400,
        code: str | None = None,
        details: dict | None = None,
        trace_id: str | None = None,
    ) -> APIResponse:
        """Return a standardised error response.

        The body always includes ``status``, ``error_code``, ``message``,
        and ``trace_id`` so callers can rely on a predictable shape.
        ``code`` is preserved as an alias for ``error_code`` for backward
        compatibility with existing consumers.

        Args:
            message: Human-readable error description.
            status_code: HTTP status code (default 400).
            code: Machine-readable error code string (e.g. ``"auth_failed"``).
            details: Optional extra context dict appended to the body.
            trace_id: Optional correlation ID; aids distributed tracing.

        Returns:
            A new :class:`APIResponse` with the standardised error envelope.
        """
        error_code = (code or "error").upper().replace("-", "_")
        body: dict[str, Any] = {
            "status": "error",
            "error_code": error_code,
            "message": message,
            "trace_id": trace_id or "",
            # Legacy keys kept for backward compatibility
            "success": False,
            "code": code or "error",
        }
        if details:
            body["details"] = details
        return cls(status_code=status_code, body=body)

    def to_aiohttp_response(self) -> web.Response:
        """转换为 aiohttp 响应"""
        return web.json_response(self.body, status=self.status_code, headers=self.headers)
