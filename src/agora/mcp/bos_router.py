"""BOSRouter — 统一 BOS URI 注册表 (P45 W2)
=================================================
合并 POC_SERVICES (子进程) 和 ProxyManager (MCP 代理) 两张表，
使用 Trie 前缀索引提供 O(k) 最长前缀匹配路由入口。

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

# Trie 路由节点标记
_ROUTE_MARKER = "__route__"


class BOSRouter:
    """统一 BOS URI 路由核心。

    - POC routes: 从 bos_resolver.POC_SERVICES 加载 (子进程)
    - Proxy routes: 从 ProxyManager 加载 (MCP 代理)
    - 使用 Trie 前缀索引，resolve 时间复杂度 O(k) 其中 k=URI seg 数
    """

    def __init__(self):
        self._routes: dict[str, dict[str, Any]] = {}
        # Trie: nested dict, 叶子节点含 _ROUTE_MARKER
        self._trie: dict[str, Any] = {}

    # ── Trie 操作 ─────────────────────────────────────

    def _trie_insert(self, prefix: str, route: dict[str, Any]) -> None:
        """按 URI 段逐级插入 trie."""
        segments = self._uri_segments(prefix)
        node = self._trie
        for seg in segments:
            node = node.setdefault(seg, {})
        node[_ROUTE_MARKER] = route

    def _trie_remove(self, prefix: str) -> None:
        """从 trie 移除路由 (不清除空节点，简化实现)."""
        segments = self._uri_segments(prefix)
        node = self._trie
        for seg in segments:
            if seg not in node:
                return  # 不在 trie 中
            node = node[seg]
        node.pop(_ROUTE_MARKER, None)

    def _trie_lookup(self, uri: str) -> dict[str, Any] | None:
        """Trie 最长前缀匹配 — O(k) 遍历，k = URI段数.

        返回最深匹配路径上的 __route__ 节点作为最佳 prefix 匹配。
        """
        segments = self._uri_segments(uri)
        node = self._trie
        best = node.get(_ROUTE_MARKER)  # 根节点匹配 (bos:)

        for seg in segments:
            # 当前节点的通配符: 作为回退记录
            if "" in node and _ROUTE_MARKER in node[""]:
                best = node[""][_ROUTE_MARKER]

            if seg in node:
                node = node[seg]
                if _ROUTE_MARKER in node:
                    best = node[_ROUTE_MARKER]
                continue

            # 当前段不通: 尝试通配符
            if "" in node:
                node = node[""]
                if _ROUTE_MARKER in node:
                    best = node[_ROUTE_MARKER]
                continue

            break

        # 末尾空段回退: 检查有无 "" child (斜杠注册)
        if _ROUTE_MARKER not in node and "" in node:
            if _ROUTE_MARKER in node[""]:
                best = node[""][_ROUTE_MARKER]

        # 精确匹配: 注册时自动加 / 但 URI 没 /
        if best is None and not uri.endswith("/"):
            node = self._trie
            for seg in segments:
                if seg in node:
                    node = node[seg]
                else:
                    return None
            if _ROUTE_MARKER in node:
                best = node[_ROUTE_MARKER]
            elif "" in node and _ROUTE_MARKER in node[""]:
                best = node[""][_ROUTE_MARKER]

        return best

    @staticmethod
    def _uri_segments(uri: str) -> list[str]:
        """将 bos:// URI 拆分为段列表。

        bos://memory/kos/search → ["bos:", "memory", "kos", "search"]
        bos://memory/kos/      → ["bos:", "memory", "kos", ""]
        """
        if uri.startswith("bos://"):
            rest = uri[6:]  # strip "bos://" (6 chars)
        else:
            rest = uri
        parts = rest.split("/")
        result = ["bos:"]
        for i, p in enumerate(parts):
            if p:
                result.append(p)
            elif i == len(parts) - 1:  # trailing slash preserves empty
                result.append("")
        # edge: only bos:// → just ["bos:"]
        if len(result) == 1:
            result.append("")
        return result

    # ── 公共 API ───────────────────────────────────────

    def register(
        self, prefix: str, adapter: str, config: dict[str, Any] | None = None
    ) -> None:
        """注册一条路由。

        Args:
            prefix: BOS URI 前缀 (e.g. bos://memory/kos/ or bos://memory/kos/search)
            adapter: 适配器类型 poc|proxy|internal|http
            config: 额外配置
        """
        if not prefix.endswith("/"):
            prefix += "/"
        if prefix in self._routes:
            _log.warning(
                "[BOSRouter] Skipping duplicate: %s (already %s)",
                prefix,
                self._routes[prefix]["adapter"],
            )
            return
        route = {
            "adapter": adapter,
            "prefix": prefix,
            "config": config or {},
        }
        self._routes[prefix] = route
        self._trie_insert(prefix, route)
        _log.info("[BOSRouter] Registered: %s → %s", prefix, adapter)

    def unregister(self, prefix: str) -> None:
        """注销路由。"""
        if not prefix.endswith("/"):
            prefix += "/"
        self._routes.pop(prefix, None)
        self._trie_remove(prefix)

    def resolve(self, uri: str) -> dict[str, Any] | None:
        """最长前缀匹配 — 使用 Trie O(k) 索引。"""
        return self._trie_lookup(uri)

    def list_all(self, prefix_filter: str = "") -> list[dict[str, Any]]:
        """列出所有路由，可选前缀过滤。"""
        result = []
        for prefix, route in self._routes.items():
            if prefix_filter and not prefix.startswith(prefix_filter):
                continue
            result.append(
                {
                    "prefix": prefix,
                    "adapter": route["adapter"],
                    "config": route.get("config", {}),
                }
            )
        result.sort(key=lambda r: r["prefix"])
        return result

    def count(self) -> int:
        return len(self._routes)

    def stats(self) -> dict[str, int]:
        """按 adapter 类型统计。"""
        from collections import Counter

        c = Counter(r["adapter"] for r in self._routes.values())
        return dict(c)

    def seed_from_poc(self, poc_services: dict) -> int:
        """从 POC_SERVICES 字典批量注册路由。

        Args:
            poc_services: bos_resolver.POC_SERVICES 字典

        Returns:
            新注册的路由数量
        """
        count = 0
        for uri, svc in poc_services.items():
            self.register(
                uri,
                adapter="poc",
                config={
                    "domain": getattr(svc, "domain", ""),
                    "transport": getattr(svc, "transport", ""),
                    "description": getattr(svc, "description", ""),
                },
            )
            count += 1
        _log.info("BOSRouter seeded from POC: %d routes", count)
        return count

    def reload_from_m1(self) -> int:
        """热加载: 从 M1 Workflow YAML 重新注册 (不重启服务器).

        新增的 WORKFLOW-*.yaml 会被注册，已有路由不被覆盖。
        返回新注册数量。

        用法:
            from agora.mcp.bos_router import bos_router
            count = bos_router.reload_from_m1()
        """
        from agora.mcp.bos_auto_register import auto_register_from_m1

        count = auto_register_from_m1(bos_router=self)
        _log.info("[BOSRouter] reload_from_m1: %d new routes", count)
        return count

    def reload_from_discovery(self) -> int:
        """热加载: 从 AGENTS.md 重新发现 (不重启服务器).

        返回新注册数量。
        """
        from agora.mcp.bos_discovery import discover_from_workspace

        count = discover_from_workspace()
        _log.info("[BOSRouter] reload_from_discovery: %d new routes", count)
        return count


# ── 全局单例 ──
bos_router = BOSRouter()
