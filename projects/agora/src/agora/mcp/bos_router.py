"""BOSRouter — 统一 BOS URI 注册表 (P45 W2)
=================================================
合并 POC_SERVICES (子进程) 和 ProxyManager (MCP 代理) 两张表，
提供最长前缀匹配的统一路由入口。

用法:
    from agora.mcp.bos_router import BOSRouter, bos_router

    route = bos_router.resolve("bos://memory/kos/search")
    → {"adapter": "poc", "service_name": "kos-search", "prefix": "bos://memory/kos/search"}

    routes = bos_router.list_all(prefix="bos://analysis/")
    → [{"uri": "bos://analysis/minerva/research", ...}]
"""

from __future__ import annotations

import logging
from typing import Any

_log = logging.getLogger(__name__)


class BOSRouter:
    """统一 BOS URI 路由核心。

    - POC routes: 从 bos_resolver.POC_SERVICES 加载 (子进程)
    - Proxy routes: 从 ProxyManager 加载 (MCP 代理)
    - 最长前缀匹配
    """

    def __init__(self):
        self._routes: dict[str, dict[str, Any]] = {}

    def register(self, prefix: str, adapter: str, config: dict[str, Any] | None = None) -> None:
        """注册一条路由。

        Args:
            prefix: BOS URI 前缀 (e.g. bos://memory/kos/ or bos://memory/kos/search)
            adapter: 适配器类型 poc|proxy|internal|http
            config: 额外配置
        """
        if not prefix.endswith("/"):
            prefix += "/"
        if prefix in self._routes:
            _log.warning("[BOSRouter] Skipping duplicate: %s (already %s)", prefix, self._routes[prefix]["adapter"])
            return
        self._routes[prefix] = {
            "adapter": adapter,
            "prefix": prefix,
            "config": config or {},
        }
        _log.info("[BOSRouter] Registered: %s → %s", prefix, adapter)

    def unregister(self, prefix: str) -> None:
        """注销路由。"""
        if not prefix.endswith("/"):
            prefix += "/"
        self._routes.pop(prefix, None)

    def resolve(self, uri: str) -> dict[str, Any] | None:
        """最长前缀匹配 — 返回路由信息或 None。"""
        best_match = None
        best_len = -1
        for prefix, route in self._routes.items():
            if uri.startswith(prefix) and len(prefix) > best_len:
                best_match = route
                best_len = len(prefix)
        return best_match

    def list_all(self, prefix_filter: str = "") -> list[dict[str, Any]]:
        """列出所有路由，可选前缀过滤。"""
        result = []
        for prefix, route in self._routes.items():
            if prefix_filter and not prefix.startswith(prefix_filter):
                continue
            result.append({
                "prefix": prefix,
                "adapter": route["adapter"],
                "config": route.get("config", {}),
            })
        result.sort(key=lambda r: r["prefix"])
        return result

    def count(self) -> int:
        return len(self._routes)

    def stats(self) -> dict[str, int]:
        """按 adapter 类型统计。"""
        from collections import Counter
        c = Counter(r["adapter"] for r in self._routes.values())
        return dict(c)


# ── 全局单例 ──
bos_router = BOSRouter()
