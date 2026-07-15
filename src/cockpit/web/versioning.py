"""cockpit.web.versioning — API 版本管理

提供 API 版本装饰器、版本路由、兼容性检查和 OpenAPI 文档生成。
支持多版本共存，弃用版本警告，以及版本升级路径追踪。

Usage:
    from cockpit.web.versioning import version_manager, api_version

    @api_version("v1")
    @router.get("/projects")
    def list_projects_v1():
        return {"version": "v1", "projects": ["ecos", "omo", "agora"]}

    @api_version("v2")
    @router.get("/projects")
    def list_projects_v2():
        return {"version": "v2", "projects": [
            {"id": "ecos", "layer": "L0"},
            {"id": "omo", "layer": "L2"},
        ]}
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from datetime import datetime
from functools import wraps
from typing import Any

from fastapi import FastAPI, Request, Response

logger = logging.getLogger("cockpit.versioning")

# ── 版本注册表 ─────────────────────────────────────────────────
API_VERSIONS: dict[str, dict[str, Callable]] = {}
DEPRECATED_VERSIONS: set[str] = set()
VERSION_REGISTRY_PATH: str = ""


class VersionManager:
    """API 版本管理器

    管理 API 路由的版本注册、弃用标记和版本信息查询。
    """

    def __init__(self):
        self.versions: dict[str, dict[str, Callable]] = {}
        self.deprecated: set[str] = set()
        self._current_version: str = ""

    @property
    def current_version(self) -> str:
        """当前 API 版本，从注册版本中取最大值"""
        if self._current_version:
            return self._current_version
        if self.versions:
            all_vers = set()
            for handlers in self.versions.values():
                all_vers.update(handlers.keys())
            if all_vers:
                self._current_version = max(all_vers)
        return self._current_version or "v1"

    def register(self, path: str, version: str, handler: Callable) -> None:
        """注册一个 API 版本 handler"""
        if path not in self.versions:
            self.versions[path] = {}
        self.versions[path][version] = handler
        logger.info("Registered %s for %s", version, path)

    def get_handler(self, path: str, version: str = "latest") -> Callable | None:
        """获取指定路径和版本的 handler"""
        if path not in self.versions:
            return None

        available = sorted(self.versions[path].keys())

        if version == "latest":
            return self.versions[path][available[-1]]

        if version in self.versions[path]:
            # 检查是否弃用
            if version in self.deprecated:
                logger.warning("Deprecated version %s used for %s", version, path)
            return self.versions[path][version]

        # 版本不存在，尝试降级到最近的兼容版本
        for v in reversed(available):
            if v < version:
                logger.info("Falling back %s -> %s for %s", version, v, path)
                return self.versions[path][v]

        return None

    def deprecate(self, version: str) -> None:
        """标记一个版本为弃用"""
        self.deprecated.add(version)
        logger.info("Deprecated API version %s", version)

    def get_version_info(self) -> dict[str, Any]:
        """获取版本信息"""
        all_versions = set()
        for handlers in self.versions.values():
            all_versions.update(handlers.keys())

        return {
            "current_version": self.current_version,
            "supported_versions": sorted(all_versions),
            "deprecated_versions": sorted(self.deprecated),
            "endpoints": len(self.versions),
            "updated_at": datetime.now().isoformat(),
        }

    def get_version_history(self) -> list[dict[str, Any]]:
        """获取版本历史（用于追踪升级路径）"""
        history = []
        for v in sorted(set(v for handlers in self.versions.values() for v in handlers.keys())):
            endpoints = [{"path": p, "version": v} for p, handlers in self.versions.items() if v in handlers]
            history.append(
                {
                    "version": v,
                    "deprecated": v in self.deprecated,
                    "endpoints": len(endpoints),
                    "endpoint_list": endpoints,
                }
            )
        return history


# ── 全局实例 ───────────────────────────────────────────────────
version_manager = VersionManager()


# ── 装饰器 ─────────────────────────────────────────────────────
def api_version(version: str):
    """API 版本装饰器

    标记一个 API handler 所属的版本。

    Usage:
        @api_version("v1")
        @router.get("/path")
        async def handler(): ...
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return func(*args, **kwargs)

        wrapper._api_version = version  # type: ignore[attr-defined]
        return wrapper

    return decorator


# ── FastAPI 集成 ────────────────────────────────────────────────
def setup_version_middleware(app: FastAPI) -> None:
    """为 FastAPI 应用添加版本管理中间件

    功能：
    - 版本检查：提取 X-API-Version 头或 URL 路径版本
    - 弃用警告：在响应头中添加弃用信息
    - 版本信息端点：/api/version

    Args:
        app: FastAPI 应用实例
    """

    @app.middleware("http")
    async def version_middleware(request: Request, call_next: Callable) -> Response:
        """版本管理中间件"""
        response = await call_next(request)

        path = request.url.path

        # 只对 API 路径添加版本信息
        if path.startswith("/api/") and path != "/api/version":
            version_info = version_manager.get_version_info()
            response.headers["X-API-Version"] = version_info["current_version"]

            # 检查请求版本是否弃用
            req_version = request.headers.get("X-API-Version", "")
            if req_version in version_manager.deprecated:
                response.headers["X-API-Deprecated"] = req_version
                response.headers["X-API-Suggested-Version"] = version_info["current_version"]

        return response

    @app.get("/api/version")
    async def version_endpoint() -> dict[str, Any]:
        """API 版本信息端点"""
        return version_manager.get_version_info()

    @app.get("/api/version/history")
    async def version_history_endpoint() -> list[dict[str, Any]]:
        """API 版本历史端点"""
        return version_manager.get_version_history()


def generate_openapi_spec(app: FastAPI) -> dict[str, Any]:
    """生成 OpenAPI 3.0 规范文档"""
    current = version_manager.current_version
    spec = {
        "openapi": "3.0.3",
        "info": {
            "title": "Cockpit API",
            "version": current,
            "description": f"eCOS v6 Cockpit API. Current version: {current}",
        },
        "paths": {},
    }

    # 从 FastAPI 路由表提取路径
    for route in app.routes:
        if hasattr(route, "path") and route.path.startswith("/api/"):
            methods = getattr(route, "methods", set()) or set()
            methods_str = [m.lower() for m in methods if m not in {"HEAD", "OPTIONS"}]
            if methods_str:
                spec["paths"][route.path] = {
                    m: {
                        "summary": f"{m.upper()} {route.path}",
                        "responses": {"200": {"description": "Success"}},
                        "tags": ["api"],
                    }
                    for m in methods_str
                }

    return spec
