"""BOS URI 解析器 — 公共 API"""

from __future__ import annotations

import logging
import os
import threading
from concurrent.futures import Future
from pathlib import Path
from typing import Any

from .adapter import get_stdio_adapter
from .services import BOS_URI_DOMAIN_PATTERN, POC_SERVICES, BosService

_log = logging.getLogger(__name__)

_WS = os.environ.get("WORKSPACE_ROOT") or str(Path.home() / "Workspace")


def _run_sync_with_timeout(func: Any, timeout: float) -> Any:
    """在线程中执行同步函数并带超时；超时后返回/抛异常，工作线程设为 daemon 不阻塞事件循环关闭."""
    fut: Future[Any] = Future()

    def _target() -> None:
        try:
            fut.set_result(func())
        except BaseException as exc:
            fut.set_exception(exc)

    t = threading.Thread(target=_target, daemon=True)
    t.start()
    return fut.result(timeout=timeout)


def normalize_bos_uri(uri: str) -> str:
    """Map legacy BOS URIs onto their canonical compatibility URI."""
    _LEGACY_PERSONA_BRIDGE_URI_PREFIX = "bos://persona/sharedbrain-bridge/"
    _CANONICAL_PERSONA_BRIDGE_URI_PREFIX = "bos://persona/sot-bridge-persona/"

    _LEGACY_BOS_URI_ALIASES = {
        f"{_LEGACY_PERSONA_BRIDGE_URI_PREFIX}recall-entity": f"{_CANONICAL_PERSONA_BRIDGE_URI_PREFIX}recall-entity",
        f"{_LEGACY_PERSONA_BRIDGE_URI_PREFIX}recall": f"{_CANONICAL_PERSONA_BRIDGE_URI_PREFIX}recall",
        f"{_LEGACY_PERSONA_BRIDGE_URI_PREFIX}sync": f"{_CANONICAL_PERSONA_BRIDGE_URI_PREFIX}sync",
    }
    return _LEGACY_BOS_URI_ALIASES.get(uri, uri)


def parse_bos_uri(uri: str) -> dict[str, str]:
    """Parse a BOS URI into its components.

    保持与 services.BOS_URI_PATTERN 的 domain 集合一致，但要求 action 存在
    (本函数用于解析完整服务 URI, 而非 domain/package 前缀).
    """
    import re

    pattern = re.compile(
        rf"^bos://(?P<domain>{BOS_URI_DOMAIN_PATTERN})"
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


def _run_maybe_async(result):
    """sync/async 兼容: coroutine 则 asyncio.run, 否则原样返回.

    BOS internal wrapper 调的目标函数可能 sync 或 async (register_service/get_status),
    此 helper 统一处理 (消除各 wrapper 重复的 iscoroutine+run 模式).
    """
    import asyncio

    return asyncio.run(result) if asyncio.iscoroutine(result) else result


def list_backend_health() -> dict:
    """backend 健康状态 (调 _health_checker 单例, robust 兜底).

    整合 bos://system/backends/health internal transport (TASK-9B363829).
    """
    try:
        from agora.auth.mcp_gateway import _health_checker

        if _health_checker is None:
            return {"status": "unavailable", "reason": "health_checker not initialized"}
        result = _run_maybe_async(_health_checker.get_all_status())
        return {"status": "ok", "backends": result}
    except Exception as e:  # defensive fallback
        return {"status": "error", "error": f"{type(e).__name__}: {e}"}


def get_bos_contract_health(yaml_path: str = "") -> dict:
    """BOS Contract 健康度 (Phase 1, ADR-0110).

    Subprocess 跑 `mof contract-lint --json` 解析 bos-services.yaml, 映射 status:
      - success → GREEN (零 error)
      - warning → YELLOW (零 error, 有 warning)
      - error   → RED (有 error, 当前 19 个 INTERNAL_MODULE_NOT_FOUND)

    Args:
        yaml_path: 留空用默认 (projects/agora/etc/bos-services.yaml).

    Returns:
        dict with keys: status, summary, raw (full mof output), error (if any).
    """
    import json
    import os
    import subprocess
    from pathlib import Path

    try:
        # Resolve yaml path (relative to workspace root or absolute)
        repo_root = Path(
            os.environ.get("WORKSPACE_ROOT", str(Path.home() / "Workspace"))
        )
        if yaml_path:
            yaml_full = Path(yaml_path)
            if not yaml_full.is_absolute():
                yaml_full = repo_root / yaml_path
        else:
            yaml_full = repo_root / "projects" / "agora" / "etc" / "bos-services.yaml"

        if not yaml_full.exists():
            return {
                "status": "RED",
                "error": f"bos-services.yaml not found: {yaml_full}",
            }

        # Run mof-contract-lint --json from projects/ecos cwd
        result = subprocess.run(
            ["uv", "run", "mof-contract-lint", "--json", "--bos-yaml", str(yaml_full)],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(repo_root / "projects" / "ecos"),
        )
        if result.returncode not in (0, 1):
            return {
                "status": "RED",
                "error": f"mof-contract-lint exit {result.returncode}: {result.stderr[:200]}",
            }

        try:
            lint_report = json.loads(result.stdout)
        except json.JSONDecodeError as e:
            return {
                "status": "RED",
                "error": f"JSON parse failed: {e}",
                "raw": result.stdout[:200],
            }

        return {
            "status": lint_report.get("status", "RED").upper(),
            "summary": lint_report.get("summary", {}),
            "raw": lint_report,
        }
    except subprocess.TimeoutExpired:
        return {"status": "RED", "error": "mof-contract-lint timeout (>30s)"}
    except Exception as e:  # defensive fallback
        return {"status": "RED", "error": f"{type(e).__name__}: {e}"}


def governance_status() -> dict:
    """治理状态 (调 Orchestrator, robust 兜底).

    整合 bos://system/governance/status internal transport.
    """
    try:
        from agora.mcp_registry.orchestrator import Orchestrator
        from agora.mcp_registry.repository import ToolCatalog

        orch = Orchestrator(ToolCatalog())
        result = _run_maybe_async(orch.get_status())
        return {"status": "ok", "governance": result}
    except Exception as e:  # defensive fallback
        return {"status": "error", "error": f"{type(e).__name__}: {e}"}


def register_backend(name: str = "", endpoint: str = "") -> dict:
    """注册 backend (调 register_service, async + robust).

    整合 bos://system/backends/register internal transport.
    """
    try:
        from agora.server.tools_registry import register_service

        result = _run_maybe_async(
            register_service(name or "default", mcp_endpoint=endpoint)
        )
        return {"status": "ok", "registered": result}
    except Exception as e:  # defensive fallback
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
    except Exception as e:  # defensive fallback
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
    except Exception as e:  # defensive fallback
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
    except Exception as e:  # defensive fallback
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
    except Exception as e:  # defensive fallback
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
            "uri": uri,
            "transport": service.transport,
        }

    result: dict
    if service.transport == "internal":
        # internal transport: 同进程 importlib, 统一加超时防止挂死
        try:
            import asyncio as _asyncio
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
            has_pm = "proxy_manager" in sig.parameters

            def _invoke() -> Any:
                if has_pm:
                    return func(*args, proxy_manager=proxy_manager, **kwargs)
                return func(*args, **kwargs)

            loop = _asyncio.get_running_loop()
            raw = await loop.run_in_executor(
                None, lambda: _run_sync_with_timeout(_invoke, timeout=10.0)
            )
            if inspect.isawaitable(raw):
                raw = await raw
            result = {"status": "ok", "result": raw}
        except TimeoutError:
            result = {
                "status": "error",
                "error": f"internal_bos_service_timeout: {uri}",
            }
        except Exception as e:  # defensive fallback
            result = {"status": "error", "error": str(e)}
    else:
        result = invoke_stdio(uri, *args, **kwargs)

    result["uri"] = uri
    result["transport"] = service.transport
    return result
