"""BOS URI 解析器 — 公共 API"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from .services import POC_SERVICES, BosService
from .adapter import get_stdio_adapter

_log = logging.getLogger(__name__)

_WS = str(Path.home() / "Workspace")


def normalize_bos_uri(uri: str) -> str:
    """Map legacy BOS URIs onto their canonical compatibility URI."""
    from agora.legacy_compat import (
        CANONICAL_PERSONA_BRIDGE_URI_PREFIX,
        LEGACY_PERSONA_BRIDGE_URI_PREFIX,
    )

    _LEGACY_BOS_URI_ALIASES = {
        f"{LEGACY_PERSONA_BRIDGE_URI_PREFIX}recall-entity": f"{CANONICAL_PERSONA_BRIDGE_URI_PREFIX}recall-entity",
        f"{LEGACY_PERSONA_BRIDGE_URI_PREFIX}recall": f"{CANONICAL_PERSONA_BRIDGE_URI_PREFIX}recall",
        f"{LEGACY_PERSONA_BRIDGE_URI_PREFIX}sync": f"{CANONICAL_PERSONA_BRIDGE_URI_PREFIX}sync",
    }
    return _LEGACY_BOS_URI_ALIASES.get(uri, uri)


def parse_bos_uri(uri: str) -> dict[str, str]:
    """Parse a BOS URI into its components."""
    import re

    pattern = re.compile(
        r"^bos://(?P<domain>memory|governance|omo|analysis|persona|capability|forge|meta|ecos|agora)"
        r"/(?P<package>[a-z][a-z0-9-]+)/(?P<action>[a-z][a-z0-9-]+)$"
    )
    m = pattern.match(uri)
    if not m:
        return {}
    return m.groupdict()


def list_services() -> list[dict]:
    """列出所有已注册的 BOS 服务."""
    return [
        {
            "uri": s.uri,
            "domain": s.domain,
            "package": s.package,
            "action": s.action,
            "transport": s.transport,
            "description": s.description,
            "alive": True,
        }
        for s in POC_SERVICES
    ]


def list_backend_health() -> dict:
    """backend 健康状态 (调 _health_checker 单例, robust 兜底).

    整合 bos://system/backends/health internal transport (TASK-9B363829).
    """
    try:
        from agora.auth.mcp_gateway import _health_checker

        if _health_checker is None:
            return {"status": "unavailable", "reason": "health_checker not initialized"}
        result = _health_checker.get_all_status()
        import asyncio

        if asyncio.iscoroutine(result):
            result = asyncio.run(result)
        return {"status": "ok", "backends": result}
    except Exception as e:
        return {"status": "error", "error": f"{type(e).__name__}: {e}"}


def governance_status() -> dict:
    """治理状态 (调 Orchestrator, robust 兜底).

    整合 bos://system/governance/status internal transport.
    """
    try:
        from agora.mcp_registry.orchestrator import Orchestrator
        from agora.mcp_registry.repository import ToolCatalog

        orch = Orchestrator(ToolCatalog())
        result = orch.get_status()
        import asyncio

        if asyncio.iscoroutine(result):
            result = asyncio.run(result)
        return {"status": "ok", "governance": result}
    except Exception as e:
        return {"status": "error", "error": f"{type(e).__name__}: {e}"}


def register_backend(name: str = "", endpoint: str = "") -> dict:
    """注册 backend (调 register_service, async + robust).

    整合 bos://system/backends/register internal transport.
    """
    try:
        import asyncio

        from agora.server.tools_registry import register_service

        result = register_service(name or "default", mcp_endpoint=endpoint)
        if asyncio.iscoroutine(result):
            result = asyncio.run(result)
        return {"status": "ok", "registered": result}
    except Exception as e:
        return {"status": "error", "error": f"{type(e).__name__}: {e}"}


def governance_heartbeat(max_age: float = 300) -> dict:
    """治理心跳 (查过期 heartbeat, 调 ServiceRegistry.stale_heartbeats).

    整合 bos://system/governance/heartbeat internal transport.
    """
    try:
        from agora.core.registry import ServiceRegistry

        reg = ServiceRegistry()
        stale = reg.stale_heartbeats(max_age)
        return {"status": "ok", "stale_count": len(stale), "stale": stale}
    except Exception as e:
        return {"status": "error", "error": f"{type(e).__name__}: {e}"}


def reload_routes(yaml_path: str = "") -> dict:
    """重载 BOS 路由 (调 bos_reload_routes, async + robust).

    整合 bos://system/routes/reload internal transport.
    """
    try:
        from agora.mcp.resolver.services import POC_SERVICES, _load_services

        # 真重载 BOS services (从 YAML), 同 bos_reload_routes 但不经 @mcp.tool wrap
        services = _load_services()
        POC_SERVICES.clear()
        POC_SERVICES.extend(services)
        return {"status": "ok", "reloaded": len(POC_SERVICES)}
    except Exception as e:
        return {"status": "error", "error": f"{type(e).__name__}: {e}"}


def omo_debt_summary() -> dict:
    """OMO 债务摘要 (调 omo.debt_summary, 跨包 omo).

    整合 bos://system/omo/debt internal transport.
    """
    try:
        import subprocess

        # omo 跨包, agora 通过 subprocess 调 (CLAUDE.md: omo 依赖声明但 subprocess 调用)
        result = subprocess.run(
            ["omo", "debt", "list"], capture_output=True, text=True, timeout=10
        )
        return {
            "status": "ok" if result.returncode == 0 else "error",
            "exit_code": result.returncode,
            "stdout": result.stdout[:500],
            "stderr": result.stderr[:200] if result.stderr else "",
        }
    except Exception as e:
        return {"status": "error", "error": f"{type(e).__name__}: {e}"}


def get_service(uri: str) -> BosService | None:
    """通过 URI 查找 BOS 服务."""
    norm = normalize_bos_uri(uri)
    for s in POC_SERVICES:
        if s.uri == norm:
            return s
    return None


def list_domains() -> dict[str, list[str]]:
    """列出所有域及其 URI."""
    domains: dict[str, list[str]] = {}
    for s in POC_SERVICES:
        domains.setdefault(s.domain, []).append(s.uri)
    return domains


def invoke_stdio(uri: str, *args: Any, **kwargs: Any) -> dict:
    """通过 stdio 调用 BOS 服务 (兼容旧接口)."""
    service = get_service(uri)
    if not service:
        return {"uri": uri, "status": "error", "error": f"unknown_bos_uri: {uri}"}
    adapter = get_stdio_adapter()
    result = adapter.call(service, *args, **kwargs)
    if isinstance(result, dict) and "uri" not in result:
        result["uri"] = uri
    return result


def protocol_self_check() -> dict:
    """自检: 验证所有服务定义."""
    from collections import Counter

    domains = Counter(s.domain for s in POC_SERVICES)
    return {
        "status": "ok",
        "total": len(POC_SERVICES),
        "domains": dict(domains),
        "by_transport": dict(Counter(s.transport for s in POC_SERVICES)),
    }


async def resolve_bos_uri(
    uri: str, *args: Any, proxy_manager: Any | None = None, **kwargs: Any
) -> dict:
    """异步 BOS URI 解析 — Swarm 路由感知版本 (Phase 3)."""
    # ── Step 1: 尝试通过 BOSRouter 路由 (支持远程代理) ──
    try:
        from agora.mcp.bos_router import bos_router

        route = bos_router.resolve(uri)
        if route and route.get("adapter") == "proxy" and proxy_manager:
            _log.info("[Resolver] Routing %s via ProxyManager (Swarm)", uri)
            # 通过代理层执行
            # 如果是 tools/call 风格参数
            arguments = kwargs.get("arguments", kwargs)
            if isinstance(arguments, str):
                import json

                arguments = json.loads(arguments)

            res = await proxy_manager.dispatch(uri, arguments)
            if res.get("status") == "ok":
                return res
            # 如果 proxy dispatch 失败，继续尝试本地回退
    except Exception as e:
        _log.debug("[Resolver] Router lookup failed: %s", e)

    # ── Step 2: 本地执行逻辑 (POC / Internal) ──
    service = get_service(uri)
    if not service:
        return {"status": "error", "error": f"unknown_bos_uri: {uri}"}

    if service.description.startswith("[UNIMPLEMENTED]"):
        _log.warning("[Resolver] Invoking unimplemented BOS service: %s", uri)
        return {
            "status": "error",
            "error": f"unimplemented_bos_service: {uri}",
            "description": service.description,
        }

    result: dict
    if service.transport == "internal":
        # internal transport: 同进程 importlib
        try:
            import importlib
            import inspect
            import sys

            if service.package and service.package != "agora":
                pkg_path = str(Path(_WS) / "projects" / service.package / "src")
                if pkg_path not in sys.path:
                    sys.path.insert(0, pkg_path)

            mod = importlib.import_module(service.module_path)
            func = getattr(mod, service.func_name)

            # 尝试传递 proxy_manager (Phase 3)
            sig = inspect.signature(func)
            if "proxy_manager" in sig.parameters:
                raw = func(*args, proxy_manager=proxy_manager, **kwargs)
            else:
                raw = func(*args, **kwargs)

            if inspect.isawaitable(raw):
                raw = await raw
            result = {"status": "ok", "result": raw}
        except Exception as e:
            result = {"status": "error", "error": str(e)}
    else:
        result = invoke_stdio(uri, *args, **kwargs)

    result["uri"] = uri
    result["transport"] = service.transport
    return result
