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
from collections.abc import Callable
from typing import Any

from agora.admission import evaluate_admission

_log = logging.getLogger(__name__)

# Trie 路由节点标记
_ROUTE_MARKER = "__route__"
_ADMISSION_FIELDS = frozenset(
    {
        "capability",
        "data_classification",
        "owner",
        "permission_ref",
        "resource_id",
        "role",
        "trace_id",
    }
)


class BOSRouter:
    """统一 BOS URI 路由核心。

    - POC routes: 从 bos_resolver.POC_SERVICES 加载 (子进程)
    - Proxy routes: 从 ProxyManager 加载 (MCP 代理)
    - 使用 Trie 前缀索引，resolve 时间复杂度 O(k) 其中 k=URI seg 数
    """

    def __init__(
        self,
        *,
        admission_evaluator: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
        capability_catalog: Any | None = None,
        admission_catalog: Any | None = None,
    ):
        self._routes: dict[str, list[dict[str, Any]]] = {}
        # Trie: nested dict, 叶子节点含 _ROUTE_MARKER
        self._trie: dict[str, Any] = {}
        self._admission_evaluator = admission_evaluator or evaluate_admission
        self._admission_rejections: list[dict[str, Any]] = []
        # B2 能力感知: 挂载 capability/admission catalog 后 resolve 自动走语义路由
        self._capability_catalog = capability_catalog
        self._admission_catalog = admission_catalog

    def enable_capability_gating(
        self,
        capability_catalog: Any | None = None,
        admission_catalog: Any | None = None,
    ) -> None:
        """启用 B2 能力感知路由 (capability 声明 + 准入生命周期)。

        挂载后, resolve() 自动升级为 resolve_with_capability() 语义路由:
        deprecated 声明 / retired|quarantined|discovered 生命周期 → 不路由。
        显式传入 catalog 优先; 未传则惰性加载默认实现。
        """
        if capability_catalog is None:
            try:
                from agora.mcp.capability_catalog import CapabilityCatalog

                self._capability_catalog = CapabilityCatalog()
            except Exception as exc:  # defensive fallback
                _log.debug("[BOSRouter] capability catalog unavailable: %s", exc)
        else:
            self._capability_catalog = capability_catalog
        if admission_catalog is None:
            try:
                from agora.external_connections import ExternalConnectionCatalog

                self._admission_catalog = ExternalConnectionCatalog()
            except Exception as exc:  # defensive fallback
                _log.debug("[BOSRouter] admission catalog unavailable: %s", exc)
        else:
            self._admission_catalog = admission_catalog
        _log.info("[BOSRouter] capability gating enabled (B2 semantic routing)")

    # ── Trie 操作 ─────────────────────────────────────

    def _trie_insert(self, prefix: str, route: dict[str, Any]) -> None:
        """按 URI 段逐级插入 trie."""
        segments = self._uri_segments(prefix)
        node = self._trie
        for seg in segments:
            node = node.setdefault(seg, {})
        node.setdefault(_ROUTE_MARKER, []).append(route)

    def _trie_remove(self, prefix: str) -> None:
        """从 trie 移除路由 (不清除空节点，简化实现)."""
        segments = self._uri_segments(prefix)
        node = self._trie
        for seg in segments:
            if seg not in node:
                return  # 不在 trie 中
            node = node[seg]
        node.pop(_ROUTE_MARKER, None)

    def _trie_lookup(self, uri: str) -> list[dict[str, Any]] | None:
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
        if _ROUTE_MARKER not in node and "" in node and _ROUTE_MARKER in node[""]:
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
    ) -> bool:
        """注册一条路由。

        Args:
            prefix: BOS URI 前缀 (e.g. bos://memory/kos/ or bos://memory/kos/search)
            adapter: 适配器类型 poc|proxy|internal|http
            config: 额外配置
        """
        if not prefix.endswith("/"):
            prefix += "/"
        route_config = dict(config or {})
        if prefix in self._routes:
            # 避免完全重复的注册
            for r in self._routes[prefix]:
                if r["adapter"] == adapter and r.get("config") == route_config:
                    return True

        decision = self._evaluate_route_admission(prefix, adapter, route_config)
        if decision.get("status") != "admitted":
            rejection = {
                "prefix": prefix,
                "adapter": adapter,
                "status": "rejected",
                "reasons": [str(reason) for reason in decision.get("reasons", [])],
                "provider": decision.get("provider"),
            }
            self._admission_rejections.append(rejection)
            _log.warning("[BOSRouter] Route admission rejected: %s", rejection)
            return False

        self._routes.setdefault(prefix, [])
        route = {
            "adapter": adapter,
            "prefix": prefix,
            "config": route_config,
            "admission": {
                "status": "admitted",
                "provider": decision.get("provider"),
                "policy_digest": decision.get("policy_digest"),
            },
        }
        self._routes[prefix].append(route)
        self._trie_insert(prefix, route)
        _log.info("[BOSRouter] Registered: %s → %s", prefix, adapter)
        return True

    def _evaluate_route_admission(
        self, prefix: str, adapter: str, config: dict[str, Any]
    ) -> dict[str, Any]:
        """Build a credential-free admission request for every route write."""
        admission_meta = config.get("admission", {})
        if admission_meta is None:
            admission_meta = {}
        if not isinstance(admission_meta, dict):
            return {
                "status": "rejected",
                "reasons": ["invalid_admission_metadata"],
            }
        unknown_fields = sorted(set(admission_meta) - _ADMISSION_FIELDS)
        if unknown_fields:
            return {
                "status": "rejected",
                "reasons": ["unsupported_admission_metadata"],
            }

        request: dict[str, Any] = {
            "domain": config.get("domain") or prefix.split("/", 3)[2],
            "role": admission_meta.get("role", "route_registry"),
            "capability": admission_meta.get("capability", prefix),
            "adapter": adapter,
            "source": config.get("source", "agora.bos_router"),
        }
        for key in (
            "permission_ref",
            "resource_id",
            "trace_id",
            "owner",
            "data_classification",
        ):
            if key in admission_meta:
                request[key] = admission_meta[key]
        try:
            result = self._admission_evaluator(request)
        except Exception as exc:  # noqa: BLE001 - admission must fail closed
            return {
                "status": "rejected",
                "reasons": ["admission_evaluator_error"],
                "provider": type(self._admission_evaluator).__name__,
                "error_type": type(exc).__name__,
            }
        if not isinstance(result, dict) or "status" not in result:
            return {
                "status": "rejected",
                "reasons": ["invalid_admission_result"],
            }
        return result

    def admission_rejections(self) -> list[dict[str, Any]]:
        """Return safe, immutable-by-copy admission rejection summaries."""
        return [dict(item) for item in self._admission_rejections]

    def unregister(self, prefix: str) -> None:
        """注销路由。"""
        if not prefix.endswith("/"):
            prefix += "/"
        self._routes.pop(prefix, None)
        self._trie_remove(prefix)

    def resolve(self, uri: str) -> dict[str, Any] | None:
        """最长前缀匹配 — 支持负载感知调度 (Smart Partitioning)。

        若已启用 B2 能力感知 (enable_capability_gating), 自动升级为语义路由:
        能力声明 deprecated / 准入生命周期 retired|quarantined|discovered → None。
        """
        if self._capability_catalog is not None or self._admission_catalog is not None:
            return self.resolve_with_capability(
                uri,
                capability_catalog=self._capability_catalog,
                admission_catalog=self._admission_catalog,
            )
        return self._resolve_plain(uri)

    def _resolve_plain(self, uri: str) -> dict[str, Any] | None:
        """底层最长前缀匹配 — 不含能力感知, 供 resolve_with_capability 内部复用。"""
        routes = self._trie_lookup(uri)
        if not routes:
            return None
        if len(routes) == 1:
            return routes[0]

        # 智能负载调度
        def get_load(r):
            cfg = r.get("config", {})
            node_id = cfg.get("node_id")
            if node_id:
                try:
                    from agora.mcp.swarm import get_swarm

                    orch = get_swarm()
                    # 用公开 get_node() API, 不访问 _nodes 私有属性
                    node = orch.get_node(node_id) if orch else None
                    if node is not None:
                        if not node.is_online:
                            return 9999.0
                        score = node.load_score
                        if node.health == "yellow":
                            score += 50.0
                        return score
                except ImportError:
                    pass
            return 100.0  # 默认高负载

        best = min(routes, key=get_load)
        return best

    def resolve_with_capability(
        self,
        uri: str,
        capability_catalog: Any | None = None,
        admission_catalog: Any | None = None,
    ) -> dict[str, Any] | None:
        """能力感知路由 (B2: 准入门禁 + 语义路由)。

        在常规 resolve 前, 用 capability_catalog (B1) 检查能力声明状态,
        用 admission_catalog (ExternalConnectionCatalog + register_capability, B2)
        检查生命周期准入。

        Args:
            uri: BOS URI
            capability_catalog: CapabilityCatalog 实例 (能力声明 + 使用统计)
            admission_catalog: ExternalConnectionCatalog 实例 (能力准入生命周期)

        Returns:
            路由 (admitted/sandbox 且存在) 或 None (被准入拦截/未注册)
        """
        # 1. 常规路由 (绕过能力感知, 避免递归)
        route = self._resolve_plain(uri)
        if route is None:
            return None

        # 2. 能力声明校验 (B1): status != active → 不路由
        if capability_catalog is not None:
            decl = capability_catalog.get(uri)
            if decl is not None and decl.get("status") == "deprecated":
                return None

        # 3. 能力准入 (B2): 生命周期为 retired/quarantined → 不路由
        if admission_catalog is not None:
            resource = admission_catalog.get(uri)
            if resource is not None and resource.lifecycle in {
                "retired",
                "quarantined",
                "discovered",
            }:
                return None

        return route

    def list_all(self, prefix_filter: str = "") -> list[dict[str, Any]]:
        """列出所有路由，可选前缀过滤。"""
        result = []
        for prefix, route_list in self._routes.items():
            if prefix_filter and not prefix.startswith(prefix_filter):
                continue
            for route in route_list:
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

        c = Counter(r["adapter"] for routes in self._routes.values() for r in routes)
        return dict(c)

    def seed_from_poc(self, poc_services: list) -> int:
        """从 POC_SERVICES 列表批量注册路由。

        Args:
            poc_services: bos_resolver.POC_SERVICES 列表

        Returns:
            新注册的路由数量
        """
        count = 0
        for svc in poc_services:
            uri = (
                svc.get("uri", "") if isinstance(svc, dict) else getattr(svc, "uri", "")
            )
            if not uri:
                continue
            registered = self.register(
                uri,
                adapter="poc",
                config={
                    "domain": svc.get("domain", "")
                    if isinstance(svc, dict)
                    else getattr(svc, "domain", ""),
                    "package": svc.get("package", "")
                    if isinstance(svc, dict)
                    else getattr(svc, "package", ""),
                    "action": svc.get("action", "")
                    if isinstance(svc, dict)
                    else getattr(svc, "action", ""),
                    "transport": svc.get("transport", "")
                    if isinstance(svc, dict)
                    else getattr(svc, "transport", ""),
                    "description": svc.get("description", "")
                    if isinstance(svc, dict)
                    else getattr(svc, "description", ""),
                },
            )
            count += int(registered)
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
try:  # B2: 单例默认启用能力感知语义路由 (惰性加载, 失败降级为纯路由)
    bos_router.enable_capability_gating()
except Exception:  # noqa: BLE001 - 单例初始化必须 fail-open (纯路由兜底)
    _log.warning("[BOSRouter] capability gating disabled on singleton init")


def clean_inbox_content(content: str) -> str:
    """BOS Inbox 数据脱敏与清洗屏障 v2.0 (Sanitizer - CR-DOMAIN-AUTH-01 / Anti-Injection).

    过滤规则:
    1. 剥离 <script>...</script> 与 <iframe>...</iframe> 危险 HTML 标签
    2. 过滤 javascript: 与 data:text/html 等危险伪协议连接
    3. 过滤内联 HTML 事件捕获器 (e.g. onload=, onerror=, onclick=, onmouseover=)
    4. 清洗隐藏的高危系统命令伪造控制转义序列
    """
    import re

    if not content:
        return ""
    cleaned = re.sub(
        r"<script[^>]*>[\s\S]*?</script>",
        "[SCRIPT_REMOVED_FOR_SECURITY]",
        content,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r"<iframe[^>]*>[\s\S]*?</iframe>",
        "[IFRAME_REMOVED_FOR_SECURITY]",
        cleaned,
        flags=re.IGNORECASE,
    )
    # 过滤 javascript: 与 data:text/html 伪协议
    cleaned = re.sub(
        r"javascript:", "sanitized-javascript:", cleaned, flags=re.IGNORECASE
    )
    cleaned = re.sub(
        r"data:\s*(?:text/html|application/javascript)[^\"'>\s]*",
        "[DATA_URI_REMOVED]",
        cleaned,
        flags=re.IGNORECASE,
    )
    # 阻断内联事件属性，如 onerror=, onload=, onclick=
    cleaned = re.sub(
        r"\bon[a-zA-Z]{3,}\s*=",
        "sanitized_event=",
        cleaned,
        flags=re.IGNORECASE,
    )
    # 剥离低阶非打印转义 ASCII 字符
    cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", cleaned)
    return cleaned
