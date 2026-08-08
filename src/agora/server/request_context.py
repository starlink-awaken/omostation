"""Request context helpers — 封装 fastmcp 私有 HTTP request context.

P2-6: fastmcp 的 `_current_http_request` 是私有 API (升级即碎)。
统一封装读写, mcp_entry.py 与 tools_auth.py 共用, 降低 fastmcp 升级风险。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from starlette.requests import Request

_HTTP_CONTEXT_IMPORT_ERR: Exception | None = None
try:
    from fastmcp.server.dependencies import (  # type: ignore[reportPrivateImportUsage]
        _current_http_request,
        get_http_request,
    )
except Exception as exc:  # defensive: fastmcp 版本变化时降级
    _HTTP_CONTEXT_IMPORT_ERR = exc
    _current_http_request = None  # type: ignore[assignment]
    get_http_request = None  # type: ignore[assignment]


def set_http_request(request: Any):
    """注入当前 HTTP request (供鉴权/依赖注入读取).

    Returns: context token (须在 finally 中 reset).
    """
    if _current_http_request is None:
        return None
    return _current_http_request.set(request)


def reset_http_request(token: Any) -> None:
    """清理注入的 HTTP request context."""
    if _current_http_request is not None and token is not None:
        _current_http_request.reset(token)


def get_http_request() -> Any | None:
    """读取当前 HTTP request; 无上下文时返回 None (不抛异常)."""
    if _current_http_request is None and get_http_request is None:
        return None
    try:
        if _current_http_request is not None:
            return _current_http_request.get()
    except LookupError:
        pass
    if get_http_request is not None:
        try:
            return get_http_request()
        except Exception:  # defensive
            return None
    return None


def has_http_context() -> bool:
    """是否有 HTTP 请求上下文 (进程内直接调用时为 False)."""
    return get_http_request() is not None
