"""BOS URI 工具 — BOS 路由/查询/监控/事件订阅。

依赖: _response.py 提供 _ok/_error/FORMAT_VERSION/_get_cache_ttl。
mcp.py 提供 FastMCP 实例、EventBus、ProxyManager 实例。
"""
from __future__ import annotations

import json
import os
import time as _time
from pathlib import Path
from typing import Any

import structlog
from fastmcp import FastMCP

# 响应工具
from agora.server._response import FORMAT_VERSION, _error, _get_cache_ttl, _ok

# BOS 状态对象 (import once at module init)
from agora.mcp.bos_middleware import (  # type: ignore[import-not-found]
    bos_cache,
    bos_circuit_breaker,
    bos_rate_limiter,
    config_watcher,
)
from agora.mcp.bos_metrics import bos_metrics  # type: ignore[import-not-found]
from agora.mcp.bos_resolver import (  # type: ignore[import-not-found]
    POC_SERVICES as _POC_SERVICES,
    list_services as _list_poc_services,
    resolve_bos_uri as _resolve_bos_uri,
)
from agora.mcp.bos_router import bos_router as _bos_router  # type: ignore[import-not-found]

# L0 审计 hook
import sys as _sys
_sys.path.insert(0, str(Path.home() / "Workspace" / "projects" / "ecos" / "src" / "ecos" / "ssot" / "tools"))
from mof_agora_hook import (  # type: ignore[import-not-found]
    post_audit as _bos_post_audit,
    pre_check as _bos_pre_check,
)

logger = structlog.get_logger(__name__)


def _get_proxy_manager():
    """Lazy import ProxyManager from mcp.py (avoid circular import at module level)."""
    from agora.server.mcp import _proxy_manager as _pm  # type: ignore[import-not-found]
    return _pm

# ── BOS 域鉴权 ──────────────────────────────────────────────

_BOS_DOMAIN_ACCESS: dict[str, list[str]] = {
    "memory":    ["read", "write"],
    "omo":       ["read", "write"],
    "analysis":  ["read", "write"],
    "persona":   ["read", "write"],
    "forge":     ["read", "write"],
    "meta":      ["read"],
    "ecos":      ["read"],
    "agora":     ["read"],
}

_AGORA_API_KEY = os.environ.get("AGORA_API_KEY", "")


def _bos_domain_authorized(uri: str, operation: str = "read") -> bool:
    """检查 BOS URI 的域级别权限。"""
    if not _AGORA_API_KEY:
        return True  # 本地开发模式
    domain = uri.split("/")[2] if uri.startswith("bos://") and "/" in uri else ""
    allowed = _BOS_DOMAIN_ACCESS.get(domain, [])
    return operation in allowed


# ── 路由辅助 ──────────────────────────────────────────────

async def _resolve_with_router(
    uri: str,
    proxy_manager: Any | None = None,
    **kwargs: Any,
) -> tuple[dict, str]:
    """路由解析链: BOSRouter → ProxyManager → POC_SERVICES.

    Args:
        uri: BOS URI
        proxy_manager: ProxyManager 实例 (来自 mcp.py)
        **kwargs: 传给下游服务的参数

    Returns:
        (result_dict, source_name) 其中 source_name 标明来源
    """
    # Step 1: BOSRouter 查找
    route = _bos_router.resolve(uri)
    if route is not None:
        adapter = route.get("adapter", "")
        if adapter == "poc":
            result = await _resolve_bos_uri(uri, **kwargs)
            if isinstance(result, dict) and result.get("status") == "error":
                config = route.get("config", {})
                return {
                    "uri": uri,
                    "status": "info",
                    "source": "bos_router_metadata",
                    "note": "Route registered but no executable backend (metadata only)",
                    "adapter": adapter,
                    "config": config,
                }, "bos_router_metadata"
            return result, "bos_router_poc"
        elif adapter == "proxy" and proxy_manager is not None:
            try:
                result = await proxy_manager.read_resource(uri)
                if isinstance(result, dict) and "contents" in result:
                    return result["contents"], "bos_router_proxy"
            except Exception:
                pass
        elif adapter in ("http", "internal"):
            result = await _resolve_bos_uri(uri, **kwargs)
            if isinstance(result, dict) and result.get("status") != "error":
                return result, "bos_router_fallback"
            return {
                "uri": uri,
                "status": "info",
                "source": "bos_router_metadata",
                "note": f"Route registered (adapter={adapter}) but no executable backend",
                "adapter": adapter,
                "config": route.get("config", {}),
            }, "bos_router_metadata"

    # Step 2: POC_SERVICES 直查（兼容旧版）
    result = await _resolve_bos_uri(uri, **kwargs)
    return result, "poc_services"


# ── 事件发布 ──────────────────────────────────────────────


def _bos_uri_to_event_type(uri: str) -> str:
    """将 bos:// URI 转换为事件类型。"""
    return uri.replace("://", ":").replace("/", ":")


def _publish_bos_event(bus, uri: str, operation: str, status: str = "ok",
                       duration_ms: int = 0) -> None:
    """发布 BOS URI 操作事件到总线。"""
    event_type = _bos_uri_to_event_type(uri)
    bus.publish(event_type, {
        "uri": uri,
        "operation": operation,
        "status": status,
        "duration_ms": duration_ms,
    }, source="bos")


# ═══════════════════════════════════════════════════════════
# 工具注册入口
# ═══════════════════════════════════════════════════════════


def register_bos_tools(mcp: FastMCP, bus: Any) -> None:
    """向 FastMCP 实例注册所有 BOS URI 工具。

    Args:
        mcp: FastMCP 实例
        bus: EventBus 实例 (来自 mcp.py)
    """
    # 将 bus 保存供闭包使用
    _bus_ref = bus

    # ── mutate_resource ──────────────────────────────────

    @mcp.tool()
    async def mutate_resource(uri: str, payload: str, action: str = "update") -> dict:
        """Unified BOS URI mutation protocol. Routes to downstream service via resolve_bos_uri.

        Args:
            uri: The bos:// URI to mutate.
            payload: JSON string payload.
            action: The verb (update, create, delete).
        """
        logger.info("mutate_resource", uri=uri, action=action)
        if not uri.startswith("bos://"):
            return _error(f"Invalid URI scheme. Must start with bos://. Received: {uri}")

        if not bos_rate_limiter.acquire(uri):
            return _error(f"Rate limit exceeded for: {uri}")

        ok, reason = _bos_pre_check(uri)
        if not ok:
            logger.warning("bos_pre_check_blocked", uri=uri, reason=reason)
            return _error(f"BOS pre-check failed: {reason}")

        _t0 = _time.time()
        try:
            result, source = await _resolve_with_router(
                uri,
                proxy_manager=_get_proxy_manager(),
                payload=json.loads(payload) if isinstance(payload, str) else payload,
                action=action,
            )
            _duration_ms = int((_time.time() - _t0) * 1000)
            bos_cache.invalidate(uri)
            _bos_post_audit(uri, 200, _duration_ms)
            _publish_bos_event(_bus_ref, uri, "mutate", "ok", _duration_ms)
            return _ok({"format_version": FORMAT_VERSION, "uri": uri, "action": action,
                        "source": source, "result": result})
        except Exception as e:
            _duration_ms = int((_time.time() - _t0) * 1000)
            _bos_post_audit(uri, 500, _duration_ms)
            _publish_bos_event(_bus_ref, uri, "mutate", "error", _duration_ms)
            logger.exception("mutate_resource_failed", uri=uri, action=action)
            return _error(f"Mutation failed: {e}")

    # ── resolve_bos_uri ──────────────────────────────────

    @mcp.tool()
    @bos_metrics.track("bos://")
    async def resolve_bos_uri(uri: str, arguments: str = "{}") -> dict:
        """将 BOS URI 解析为实际调用，路由到对应的后端服务。

        bos:// 支持域: memory, omo, analysis, persona, forge, meta, ecos, agora

        Args:
            uri: BOS URI (e.g. bos://memory/kos/search)
            arguments: JSON 参数字符串 (e.g. '{"query": "什么是 eCOS?"}')
        """
        if not uri.startswith("bos://"):
            return _error(f"Invalid BOS URI: {uri}")

        if not _bos_domain_authorized(uri, "read"):
            return _error(f"Access denied to domain: {uri}")

        if not bos_rate_limiter.acquire(uri):
            return _error(f"Rate limit exceeded for: {uri}")

        if bos_circuit_breaker.is_open(uri):
            return _error(f"Circuit breaker open for: {uri}")

        _t0 = _time.time()
        try:
            args = json.loads(arguments) if isinstance(arguments, str) else arguments

            cached = bos_cache.get(uri, args)
            if cached:
                bos_circuit_breaker.record_success(uri)
                return _ok({"format_version": FORMAT_VERSION, "uri": uri,
                            "source": "cache", "result": cached})

            result, source = await _resolve_with_router(uri, proxy_manager=_get_proxy_manager(), **args)
            bos_cache.set(uri, args, result, ttl=_get_cache_ttl(uri))
            bos_circuit_breaker.record_success(uri)
            _bos_post_audit(uri, 200, int((_time.time() - _t0) * 1000))
            _publish_bos_event(bus, uri, "resolve", "ok", int((_time.time() - _t0) * 1000))
            return _ok({"format_version": FORMAT_VERSION, "uri": uri,
                        "source": source, "result": result})
        except json.JSONDecodeError:
            return _error(f"Invalid JSON arguments: {arguments}")
        except Exception as e:
            bos_circuit_breaker.record_failure(uri)
            _bos_post_audit(uri, 500, int((_time.time() - _t0) * 1000))
            _publish_bos_event(bus, uri, "resolve", "error", int((_time.time() - _t0) * 1000))
            logger.exception("resolve_bos_uri_failed", uri=uri)
            return _error(f"BOS URI resolve failed: {e}")

    # ── read_resource ────────────────────────────────────

    @mcp.tool()
    @bos_metrics.track("bos://")
    async def read_resource(uri: str, arguments: str = "{}") -> dict:
        """通过 BOS URI 读取资源。先尝试 BOSRouter，回退到 ProxyManager，最后 bos_resolver。

        Args:
            uri: BOS URI (e.g. bos://memory/kos/search)
            arguments: JSON 参数字符串 (e.g. '{"query": "..."}')
        """
        if not uri.startswith("bos://"):
            return _error(f"Invalid BOS URI: {uri}")

        if not _bos_domain_authorized(uri, "read"):
            return _error(f"Access denied to domain: {uri}")

        if not bos_rate_limiter.acquire(uri):
            return _error(f"Rate limit exceeded for: {uri}")

        try:
            args = json.loads(arguments) if isinstance(arguments, str) else arguments
        except json.JSONDecodeError:
            return _error(f"Invalid JSON arguments: {arguments}")

        cached = bos_cache.get(uri, args)
        if cached:
            return _ok({"format_version": FORMAT_VERSION, "uri": uri,
                        "source": "cache", "result": cached})

        _t0 = _time.time()
        # Step 1: BOSRouter → POC 统一路由链
        try:
            result, source = await _resolve_with_router(uri, proxy_manager=_get_proxy_manager(), **args)
            if isinstance(result, dict) and result.get("status") != "error":
                bos_cache.set(uri, args, result, ttl=_get_cache_ttl(uri))
                bos_circuit_breaker.record_success(uri)
                _bos_post_audit(uri, 200, int((_time.time() - _t0) * 1000))
                _publish_bos_event(bus, uri, "read", "ok", int((_time.time() - _t0) * 1000))
                return _ok({"format_version": FORMAT_VERSION, "uri": uri,
                            "source": source, "result": result})
        except Exception:
            pass

        # Step 2: ProxyManager (MCP 下游代理)
        _pm = _get_proxy_manager()
        if _pm is not None:
            try:
                result = await _pm.read_resource(uri)
                if isinstance(result, dict) and "contents" in result:
                    bos_cache.set(uri, args, result["contents"], ttl=_get_cache_ttl(uri))
                    bos_circuit_breaker.record_success(uri)
                    _bos_post_audit(uri, 200, int((_time.time() - _t0) * 1000))
                    _publish_bos_event(bus, uri, "read", "ok", int((_time.time() - _t0) * 1000))
                    return _ok({"format_version": FORMAT_VERSION, "uri": uri,
                                "source": "proxy", "contents": result["contents"]})
            except Exception:
                pass

        # Step 3: bos_resolver (POC 子进程)
        try:
            result = await _resolve_bos_uri(uri, **args)
            bos_cache.set(uri, args, result, ttl=_get_cache_ttl(uri))
            bos_circuit_breaker.record_success(uri)
            _bos_post_audit(uri, 200, int((_time.time() - _t0) * 1000))
            _publish_bos_event(bus, uri, "read", "ok", int((_time.time() - _t0) * 1000))
            return _ok({"format_version": FORMAT_VERSION, "uri": uri,
                        "source": "bos_resolver", "result": result})
        except Exception as e:
            bos_circuit_breaker.record_failure(uri)
            _bos_post_audit(uri, 500, int((_time.time() - _t0) * 1000))
            _publish_bos_event(bus, uri, "read", "error", int((_time.time() - _t0) * 1000))
            logger.exception("read_resource_failed", uri=uri)
            return _error(f"Resource read failed: {e}")

    # ── list_bos_resources ───────────────────────────────

    @mcp.tool()
    async def list_bos_resources(prefix: str = "") -> dict:
        """列出所有可用的 BOS 资源。合并 BOSRouter + POC + ProxyManager。

        Args:
            prefix: URI 前缀过滤 (可选，如 bos://memory/)
        """
        resources = []
        # Part A: BOSRouter routes
        for route in _bos_router.list_all(prefix_filter=prefix):
            uri_val = route["prefix"].rstrip("/")
            config = route.get("config", {})
            resources.append({
                "uri": uri_val,
                "domain": config.get("domain", uri_val.split("/")[2] if "/" in uri_val else "unknown"),
                "source": "bos_router",
                "adapter": route["adapter"],
                "description": config.get("description", config.get("workflow",
                                        f"BOSRouter: {route['adapter']}")),
                "schema_available": bool(config.get("steps", 0) or config.get("workflow")),
            })
        # Part B: POC services (legacy)
        for svc in _list_poc_services():
            uri_val = svc.get("uri", "")
            if any(r["uri"] == uri_val for r in resources):
                continue
            resources.append({
                "uri": uri_val,
                "domain": svc.get("domain", ""),
                "source": "poc",
                "transport": svc.get("transport", ""),
                "description": svc.get("description", ""),
                "schema_available": False,
            })
        # Part C: ProxyManager configs
        _pm_for_list = _get_proxy_manager()
        if _pm_for_list is not None:
            for name, cfg in getattr(_pm_for_list, '_configs', {}).items():
                if isinstance(cfg, dict):
                    for bos_prefix in cfg.get("bos_prefixes", []):
                        resources.append({
                            "uri": bos_prefix,
                            "domain": bos_prefix.split("/")[2] if "/" in bos_prefix else "unknown",
                            "source": "proxy",
                            "transport": "mcp_proxy",
                            "description": cfg.get("description", f"Proxy: {name}"),
                        })
        if prefix:
            resources = [r for r in resources if r["uri"].startswith(prefix)]

        # Schema 标注
        try:
            wf_dir = Path(__file__).parent.parent.parent.parent / "ecos" / "src" / "ecos" / "ssot" / "mof" / "m1" / "workflow"
            if wf_dir.exists():
                import yaml
                known_actions = set()
                for f in wf_dir.glob("WORKFLOW-*.yaml"):
                    node = yaml.safe_load(open(f))
                    if node and node.get("type") == "Workflow":
                        for step in node.get("steps", []):
                            if step.get("action"):
                                known_actions.add(step["action"])
                for r in resources:
                    parts = r["uri"].replace("bos://", "").split("/")
                    if len(parts) >= 3:
                        pkg_action = f"{parts[1]}.{parts[2]}"
                        r["schema_available"] = pkg_action in known_actions
        except Exception:
            pass

        return _ok({"format_version": FORMAT_VERSION, "resources": resources,
                    "total": len(resources)})

    # ── list_bos_domains ─────────────────────────────────

    @mcp.tool()
    async def list_bos_domains() -> dict:
        """列出所有已注册的 BOS 域及其路由摘要。"""
        from collections import Counter
        doms: Counter = Counter()
        for svc in _list_poc_services():
            doms[svc.get("domain", "unknown")] += 1
        bos_domains: set[str] = set()
        for route in _bos_router.list_all():
            d = route.get("config", {}).get("domain", "")
            if d:
                bos_domains.add(d)
        for d in bos_domains:
            if d not in doms:
                doms[d] = sum(1 for r in _bos_router.list_all()
                              if r.get("config", {}).get("domain") == d)
        return _ok({"format_version": FORMAT_VERSION, "domains": dict(doms),
                    "description": "BOS URI 5+1+扩展域: memory/omo/analysis/persona/forge + M1 扩展",
                    "total_routes": _bos_router.count()})

    # ── get_bos_schema ───────────────────────────────────

    @mcp.tool()
    async def get_bos_schema(uri: str = "") -> dict:
        """获取 BOS URI 的参数规范。从 M1 Workflow 节点的 steps 读取。

        Args:
            uri: BOS URI 或 action 名称 (如 bos://analysis/minerva/research 或 minerva.research)
                 不传则返回所有已知 schema 摘要
        """
        import yaml
        try:
            wf_dir = Path(__file__).parent.parent.parent.parent / "ecos" / "src" / "ecos" / "ssot" / "mof" / "m1" / "workflow"
            if not wf_dir.exists():
                return _error("M1 Workflow 目录不存在")

            schemas: dict = {}
            for f in sorted(wf_dir.glob("WORKFLOW-*.yaml")):
                try:
                    node = yaml.safe_load(open(f))
                    if not node or node.get("type") != "Workflow":
                        continue
                    for step in node.get("steps", []):
                        action = step.get("action", "")
                        if not action:
                            continue
                        schemas[action] = {
                            "workflow": node.get("name", ""),
                            "action": action,
                            "description": step.get("description", ""),
                            "order": step.get("order"),
                            "input": step.get("input", {}),
                            "output": step.get("output", {}),
                            "sla": node.get("sla", {}),
                            "domain": node.get("domain", ""),
                            "layer": node.get("layer", ""),
                        }
                except Exception:
                    pass

            if uri:
                action_key = uri
                if uri.startswith("bos://"):
                    parts = uri.replace("bos://", "").split("/")
                    if len(parts) >= 3:
                        action_key = f"{parts[1]}.{parts[2]}"
                if action_key in schemas:
                    return _ok({"format_version": FORMAT_VERSION, "uri": uri,
                                "schema": schemas[action_key]})
                matches = {k: v for k, v in schemas.items() if action_key in k}
                if matches:
                    return _ok({"format_version": FORMAT_VERSION, "uri": uri,
                                "schemas": matches, "match_count": len(matches)})
                return _error(f"No schema found for: {uri}. Use get_bos_schema() without args to list all.")

            return _ok({"format_version": FORMAT_VERSION, "total_schemas": len(schemas),
                        "schemas": schemas,
                        "hint": "Use get_bos_schema('minerva.research') for specific"})
        except Exception as e:
            return _error(f"Schema lookup failed: {e}")

    # ── bos_middleware_status ────────────────────────────

    @mcp.tool()
    async def bos_middleware_status() -> dict:
        """BOS 中间件状态查询 — 限流/熔断/缓存实时状态。"""
        return _ok({
            "format_version": FORMAT_VERSION,
            "rate_limiter": bos_rate_limiter.status(),
            "circuit_breaker": {"open_circuits": bos_circuit_breaker.status()},
            "cache": bos_cache.status(),
            "router": {"total_routes": _bos_router.count(), "stats": _bos_router.stats()},
        })

    # ── bos_reload_m1 ────────────────────────────────────

    @mcp.tool()
    async def bos_reload_m1() -> dict:
        """热加载 M1 Workflow 路由 — 从 YAML 重新注册 (不重启服务器)."""
        count = _bos_router.reload_from_m1()
        logger.info("bos_reload_m1: %d new routes", count)
        return _ok({
            "format_version": FORMAT_VERSION,
            "action": "reload_m1",
            "new_routes": count,
            "total_routes": _bos_router.count(),
        })

    # ── bos_reload_discovery ─────────────────────────────

    @mcp.tool()
    async def bos_reload_discovery() -> dict:
        """热加载 Discovery 路由 — 从 AGENTS.md 重新发现 (不重启服务器)."""
        count = _bos_router.reload_from_discovery()
        logger.info("bos_reload_discovery: %d new routes", count)
        return _ok({
            "format_version": FORMAT_VERSION,
            "action": "reload_discovery",
            "new_routes": count,
            "total_routes": _bos_router.count(),
        })

    # ── bos_metrics_status ───────────────────────────────

    @mcp.tool()
    async def bos_metrics_status(prefix: str = "", format: str = "json") -> dict | str:
        """BOS 调用指标 — 支持 JSON 和 Prometheus 两种格式。

        Args:
            prefix: URI 前缀过滤
            format: "json" (默认) 或 "prometheus" (Prometheus scrape)
        """
        if format == "prometheus":
            lines = []
            status = bos_metrics.status(prefix)
            for p, s in sorted(status.items()):
                labels = p.replace("://", "_").replace("/", "_").replace("-", "_")
                lines.append("# HELP bos_calls_total Total BOS calls per prefix")
                lines.append("# TYPE bos_calls_total counter")
                lines.append(f'bos_calls_total{{prefix="{p}"}} {s["calls"]}')
                lines.append("# HELP bos_success_rate BOS success rate per prefix")
                lines.append("# TYPE bos_success_rate gauge")
                lines.append(f'bos_success_rate{{prefix="{p}"}} {s["success_rate"]}')
                lines.append("# HELP bos_latency_ms_avg Average latency per prefix")
                lines.append("# TYPE bos_latency_ms_avg gauge")
                lines.append(f'bos_latency_ms_avg{{prefix="{p}"}} {s["avg_latency_ms"]}')
            return "\n".join(lines) + "\n"
        if prefix:
            return _ok({"format_version": FORMAT_VERSION,
                        "metrics": bos_metrics.status(prefix)})
        return _ok({
            "format_version": FORMAT_VERSION,
            "summary": bos_metrics.summary(),
            "detail": bos_metrics.status(),
        })

    # ── watch_resource ───────────────────────────────────

    @mcp.tool()
    async def watch_resource(uri_pattern: str, callback_url: str = "") -> dict:
        """监听 BOS URI 的变化事件。

        当指定的 bos:// URI 被解析、读取或变更时，通过事件总线通知。
        支持通配符: bos://memory/kos/* (监听所有 kos 操作)

        Args:
            uri_pattern: BOS URI 模式 (e.g. bos://memory/kos/search 或 bos://memory/kos/*)
            callback_url: 可选 HTTP 回调 URL，事件发生时 POST 通知

        Returns:
            包含 subscription_id 的响应
        """
        if not uri_pattern.startswith("bos://"):
            return _error(f"Invalid BOS URI pattern: {uri_pattern}")

        event_pattern = _bos_uri_to_event_type(uri_pattern)
        sub_id = bus.subscribe("bos-watch", event_pattern, callback_url)

        logger.info("watch_resource_registered", uri_pattern=uri_pattern,
                    event_pattern=event_pattern, sub_id=sub_id)

        return _ok({
            "format_version": FORMAT_VERSION,
            "action": "watching",
            "uri_pattern": uri_pattern,
            "event_pattern": event_pattern,
            "subscription_id": sub_id,
            "hint": "Use get_event_log() to poll events, or provide callback_url for push delivery",
        })

    # ── unwatch_resource ────────────────────────────────

    @mcp.tool()
    def unwatch_resource(subscription_id: str) -> dict:
        """取消 BOS URI 事件监听。

        Args:
            subscription_id: watch_resource 返回的订阅 ID
        """
        bus.unsubscribe(subscription_id)
        logger.info("watch_resource_unregistered", sub_id=subscription_id)
        return _ok({
            "format_version": FORMAT_VERSION,
            "action": "unwatched",
            "subscription_id": subscription_id,
        })

    # ── list_bos_tools ──────────────────────────────────

    @mcp.tool()
    async def list_bos_tools() -> dict:
        """列出所有可用的 BOS MCP 工具及 schema — Agent 统一发现入口。"""
        tools = [
            {"name": "resolve_bos_uri", "description": "将 BOS URI 解析为实际调用，路由到后端服务", "arguments": {"uri": "BOS URI", "arguments": "JSON 参数字符串"}},
            {"name": "read_resource", "description": "通过 BOS URI 读取资源 (Proxy→POC 降级)", "arguments": {"uri": "BOS URI", "arguments": "JSON 参数字符串"}},
            {"name": "mutate_resource", "description": "通过 BOS URI 修改资源 (真路由 + L0 审计)", "arguments": {"uri": "BOS URI", "payload": "JSON 负载", "action": "update"}},
            {"name": "list_bos_resources", "description": "列出所有已注册 BOS 资源", "arguments": {"prefix": "可选前缀过滤"}},
            {"name": "list_bos_domains", "description": "列出 BOS 域及路由统计", "arguments": {}},
            {"name": "get_bos_schema", "description": "查询 BOS URI 的参数规范 (从 M1 节点)", "arguments": {"uri": "BOS URI 或 action 名"}},
            {"name": "bos_metrics_status", "description": "BOS 调用指标 (JSON/Prometheus)", "arguments": {"prefix": "可选前缀", "format": "json|prometheus"}},
            {"name": "bos_middleware_status", "description": "限流/熔断/缓存/路由实时状态", "arguments": {}},
        ]
        return _ok({"format_version": FORMAT_VERSION, "tools": tools, "total": len(tools)})
