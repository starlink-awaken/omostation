"""Agora MCP Server — unified entry point for all services.

工具分组 (35 tools → BOS/extracted to tools_bos.py, API Keys extracted to tools_api_keys.py):
  ┌─ Proxy Tools      :  extracted → server/tools_proxy.py  ✅
  ├─ Registry Tools   :  extracted → server/tools_registry.py  ✅
  ├─ BOS Tools        :  extracted → server/tools_bos.py  ✅
  ├─ API Key Tools    :  extracted → server/tools_api_keys.py  ✅
  ├─ A2A Task Tools   :  a2a_send/get/cancel/list_tasks/push_notification
  ├─ State Tools      :  get_state_transitions
  ├─ Agent Cards      :  list/get_agent_card
  ├─ Repo Tools       :  repo_search/discover/status/install/load/unload/pipeline
  ├─ Resources        :  agora_registry / agora_status / {domain}/{package}/{action}
  ├─ Execution        :  agora_execute (行 808)
  └─ AuditSubscriber  :  审计事件订阅 (内部组件, 非 MCP tool)

待拆分: AuditSubscriber / A2A / Repo → 独立 tools_*.py
拆分计划: docs/god-module-split-plan.md
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING

import structlog
from fastmcp import FastMCP
from fastmcp.server.middleware import AuthMiddleware

from agora.core.state import (  # type: ignore[import-not-found]
    get_event_bus,
    get_registry,
    get_router,
)
from agora.mcp import mcp_bootstrap  # type: ignore[import-not-found]
from agora.mcp_proxy.manager import ProxyManager  # type: ignore[import-not-found]

if TYPE_CHECKING:
    from agora.task_manager import TaskManager

# BOS URI 解析器 (P45 W1) — 统一 POC_SERVICES 路由
from agora.mcp.bos_metrics import bos_metrics  # type: ignore[import-not-found]

# BOS 中间件 (P46 W0) — 限流/熔断/缓存
from agora.mcp.bos_middleware import (  # type: ignore[import-not-found]
    bos_cache,
    bos_circuit_breaker,
    bos_rate_limiter,
    config_watcher,  # type: ignore[import-not-found]
)
from agora.mcp.bos_resolver import (
    POC_SERVICES as _POC_SERVICES,  # type: ignore[import-not-found]
)
from agora.mcp.bos_resolver import (
    resolve_bos_uri as _resolve_bos_uri,  # type: ignore[import-not-found]
)

# BOSRouter (P45 W2) — 统一路由注册表
from agora.mcp.bos_router import (
    bos_router as _bos_router,  # type: ignore[import-not-found]
)

# 响应工具 (God Module 拆分)
from agora.server._response import (
    FORMAT_VERSION,
    _error,
    _ok,
)

# BOS 工具 (God Module 拆分 — 13个工具 + 路由/事件/鉴权)
from agora.server.tools_bos import register_bos_tools

logger = structlog.get_logger(__name__)

_AGORA_API_KEY = os.environ.get("AGORA_API_KEY", "")

# Module-level component cache extracted to agora.server.dependencies


from agora.server.tools_auth import (
    get_access_token,
)
from agora.server.tools_auth import (
    require_agora_api_key as _require_agora_api_key,
)


def identity_from_auth_token() -> dict | None:
    """Backward-compatible identity resolver that respects monkeypatched mcp.get_access_token."""
    token = get_access_token()
    if token is None:
        return None

    claims = getattr(token, "claims", {}) or {}
    subject_id = (
        claims.get("sub") or claims.get("subject_id") or getattr(token, "client_id", "")
    )
    if not subject_id:
        return None

    identity: dict[str, object] = {
        "subject_id": subject_id,
        "subject_type": claims.get("subject_type") or "service",
    }
    if issuer := claims.get("iss") or claims.get("issuer"):
        identity["issuer"] = issuer
    if (
        tenant := claims.get("tenant")
        or claims.get("org")
        or getattr(token, "resource", None)
    ):
        identity["tenant"] = tenant
    return identity


def _resolve_caller_identity(caller_identity: str | dict | None) -> str | dict:
    """Backward-compatible caller identity normalization for tools_registry."""
    if caller_identity not in (None, ""):
        if isinstance(caller_identity, str):
            try:
                parsed = json.loads(caller_identity)
            except json.JSONDecodeError:
                return caller_identity
            return parsed if isinstance(parsed, dict) else caller_identity
        # caller_identity is dict (not None/"" because of the check above)
        return caller_identity  # type: ignore[return-value]

    # caller_identity is None or empty - try to derive from auth token
    derived = identity_from_auth_token()
    if derived is not None:
        return derived
    return "anonymous"
    return "anonymous"


@asynccontextmanager
async def _proxy_lifespan(server: FastMCP):
    """Initialize proxy connections within mcp.run()'s event loop."""
    from agora.server.dependencies import clear_caches, get_proxy_manager
    from agora.server.tools_proxy import proxy_sync_loop

    _sync_task = None
    _swarm = None
    try:
        await _init_proxy()
        _sync_task = asyncio.create_task(proxy_sync_loop(registry))

        # ── Swarm 启动 (P55) ──
        swarm_role = os.environ.get("AGORA_SWARM_ROLE", "")
        if swarm_role:
            from agora.mcp.swarm import SWARM_DEFAULT_PORT, get_swarm

            swarm_port = int(
                os.environ.get("AGORA_SWARM_PORT", str(SWARM_DEFAULT_PORT))
            )
            _swarm = get_swarm(role=swarm_role, port=swarm_port)
            _swarm.set_proxy_manager(get_proxy_manager())
            _swarm.start()
            logger.info("swarm_started", role=swarm_role, port=swarm_port)
    except Exception:  # defensive fallback
        logger.exception("proxy_init_in_lifespan")

    yield {}

    if _sync_task is not None:
        _sync_task.cancel()
        try:
            await _sync_task
        except asyncio.CancelledError:
            pass

    clear_caches()
    if _swarm is not None:
        _swarm.stop()
        logger.info("swarm_stopped")


from agora.middleware.middleware import FastMCPAuditMiddleware

mcp = FastMCP(
    "Agora — Service Convergence Hub",
    lifespan=_proxy_lifespan,
    mask_error_details=True,
    middleware=[AuthMiddleware(auth=_require_agora_api_key), FastMCPAuditMiddleware()],
)
registry = get_registry()
_bus = get_event_bus(registry)

# ── AuditSubscriber (moved from audit_subscriber.py) ─────────────────────

import contextlib as _contextlib
import sqlite3 as _sqlite3
import time as _time
import uuid as _uuid
from pathlib import Path as _Path

from agora.auth.identity import (
    normalize_identity as _normalize_identity,  # type: ignore[import-not-found]
)
from agora.mcp.mcp_bootstrap import (
    get_data_dir as _get_data_dir,  # type: ignore[import-not-found]
)

_AUDIT_DB = _Path(
    os.environ.get("AGORA_AUDIT_DB", str(_get_data_dir() / "agora-audit.db"))
)


class AuditSubscriber:
    """Subscribes to all EventBus events and persists them for audit."""

    def __init__(self, event_bus, registry=None, db_path=None):
        self._bus = event_bus
        self._registry = registry
        self._db_path = _Path(db_path or _AUDIT_DB)
        self._init_db()

    def _init_db(self):
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = _sqlite3.connect(str(self._db_path))
        conn.execute("""CREATE TABLE IF NOT EXISTS audit_log (
            id TEXT PRIMARY KEY, timestamp TEXT NOT NULL, event_type TEXT NOT NULL,
            source TEXT NOT NULL DEFAULT '', actor TEXT NOT NULL DEFAULT '',
            resource TEXT NOT NULL DEFAULT '', action TEXT NOT NULL DEFAULT '',
            trace_id TEXT NOT NULL DEFAULT '', payload TEXT NOT NULL DEFAULT '{}',
            risk_level TEXT NOT NULL DEFAULT 'INFO', duration_ms REAL NOT NULL DEFAULT 0.0
        )""")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_ts ON audit_log(timestamp)")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_audit_type ON audit_log(event_type)"
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_actor ON audit_log(actor)")
        conn.commit()
        conn.close()

    def _classify(self, event_type):
        parts = event_type.split(":", 1)
        category = parts[0] if len(parts) > 1 else parts[0]
        verb = parts[1] if len(parts) > 1 else "published"
        mapping = {
            "registry": {"actor": "registry", "resource": "service", "risk": "INFO"},
            "route": {"actor": "route", "resource": "route", "risk": "INFO"},
            "event": {"actor": "event", "resource": "event_bus", "risk": "INFO"},
            "pipeline": {"actor": "pipeline", "resource": "pipeline", "risk": "INFO"},
            "proxy": {"actor": "proxy", "resource": "proxy", "risk": "INFO"},
            "index": {"actor": "indexer", "resource": "index", "risk": "INFO"},
            "error": {"actor": "system", "resource": "system", "risk": "ERROR"},
            "security": {"actor": "security", "resource": "system", "risk": "CRITICAL"},
        }
        info = mapping.get(
            category, {"actor": "unknown", "resource": "event_bus", "risk": "INFO"}
        )
        return {
            "actor": info["actor"],
            "resource": info["resource"],
            "action": verb,
            "risk_level": info["risk"],
        }

    def on_event(self, event):
        event_type = event.get("type", "unknown")
        event_id = event.get("id", f"audit_{_uuid.uuid4().hex[:8]}")
        source = event.get("source", "")
        trace_id = event.get("trace_id", "")
        payload = event.get("payload", {})
        ts = event.get("time", _time.strftime("%Y-%m-%dT%H:%M:%SZ", _time.gmtime()))
        classified = self._classify(event_type)
        identity = payload.get("identity") if isinstance(payload, dict) else None
        if identity:
            classified["actor"] = _normalize_identity(identity).actor
        payload_str = json.dumps(payload, ensure_ascii=False, default=str)
        try:
            conn = _sqlite3.connect(str(self._db_path))
            conn.execute(
                "INSERT OR IGNORE INTO audit_log (id, timestamp, event_type, source, actor, resource, action, trace_id, payload, risk_level, duration_ms) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    f"{event_id}",
                    ts,
                    event_type,
                    source,
                    classified["actor"],
                    classified["resource"],
                    classified["action"],
                    trace_id,
                    payload_str,
                    classified["risk_level"],
                    payload.get("_duration_ms", 0.0),
                ),
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error("audit_write_failed", event_id=event_id, error=str(e))

    def query(self, actor="", resource="", event_type="", since="", limit=50):
        conditions: list[str] = []
        params: list = []
        if actor:
            conditions.append("actor = ?")
            params.append(actor)
        if resource:
            conditions.append("resource = ?")
            params.append(resource)
        if event_type:
            conditions.append("event_type LIKE ?")
            params.append(event_type.replace("*", "%"))
        if since:
            conditions.append("timestamp >= ?")
            params.append(since)
        where = " AND ".join(conditions) if conditions else "1=1"
        try:
            conn = _sqlite3.connect(str(self._db_path))
            conn.row_factory = _sqlite3.Row
            rows = conn.execute(
                f"SELECT * FROM audit_log WHERE {where} ORDER BY timestamp DESC LIMIT ?",
                [*params, limit],
            ).fetchall()
            conn.close()
            result = []
            for row in rows:
                entry = dict(row)
                with _contextlib.suppress(json.JSONDecodeError, TypeError):
                    entry["payload"] = json.loads(entry["payload"])
                result.append(entry)
            return result
        except Exception as e:
            logger.error("audit_query_failed", error=str(e))
            return []

    def stats(self, since=""):
        stats = {"total": 0, "by_risk": {}, "by_event_type": {}}
        try:
            conn = _sqlite3.connect(str(self._db_path))
            if since:
                rows = conn.execute(
                    "SELECT risk_level, COUNT(*) as cnt FROM audit_log WHERE timestamp >= ? GROUP BY risk_level",
                    (since,),
                ).fetchall()
                stats["total"] = sum(r[1] for r in rows)
            else:
                rows = conn.execute(
                    "SELECT risk_level, COUNT(*) as cnt FROM audit_log GROUP BY risk_level"
                ).fetchall()
                total_row = conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()
                stats["total"] = total_row[0] if total_row else 0
            stats["by_risk"] = {r[0]: r[1] for r in rows}
            type_rows = conn.execute(
                "SELECT event_type, COUNT(*) as cnt FROM audit_log GROUP BY event_type ORDER BY cnt DESC LIMIT 20"
            ).fetchall()
            stats["by_event_type"] = {r[0]: r[1] for r in type_rows}
            conn.close()
        except Exception as e:
            logger.error("audit_stats_failed", error=str(e))
        return stats


_auditor = AuditSubscriber(_bus, registry)
# Wire audit into event bus: every published event is automatically persisted
_bus.register_hook(_auditor.on_event)
router = get_router(registry, _bus)

# ── BOS Tools Registration ──────────────────────────────────────────
# 注册在 mcp 实例创建后、任何工具定义之前


register_bos_tools(mcp, _bus)

from agora.server.tools_swarm import (
    register_swarm_tools,  # type: ignore[import-not-found]
)

register_swarm_tools(mcp)

# ── Proxy / Registry / Diagnostics / Governance Tools ──────────────
# Phase 1: extracted from God Module (server/mcp.py) into focused modules.
# NOTE: imports are at module top level; registration calls are deferred
# until after _PROXY_CONFIG_PATH / _FORGE_REGISTRY_PATH are defined.
from agora.server.tools_diagnostics import register_diagnostics_tools
from agora.server.tools_governance import register_governance_tools
from agora.server.tools_proxy import (
    _set_constants as _set_proxy_constants,
)
from agora.server.tools_proxy import (
    register_proxy_tools,
)
from agora.server.tools_registry import register_registry_tools
from agora.server.tools_workspace_audit import register_workspace_audit_tools

# ── A2A Task Manager ──────────────────────────────────────────────────

_task_manager: TaskManager | None = None


def _get_task_manager() -> TaskManager:
    """Lazy-init and return the global TaskManager instance."""
    global _task_manager
    if _task_manager is None:
        from metaos.a2a.task_manager import TaskManager  # type: ignore[reportMissingImports]

        _task_manager = TaskManager(router)
    return _task_manager  # type: ignore[reportReturnType]


# ── MCP Proxy Configs ───────────────────────────────────────────────────────

# Path to enriched service config (with command/args for stdio services)
# Resolved relative to project root (same convention as registry.py's agora-services.json)
_PROXY_CONFIG_PATH = mcp_bootstrap.get_data_dir() / "agora-proxy-services.json"

# Forge asset registry path — the single source of truth for service port configs
_FORGE_REGISTRY_PATH = Path.home() / "Workspace" / "Forge" / "assets" / "registry.json"

# ── Wire in proxy/registry/diagnostics/governance tools ─────────────
_set_proxy_constants(_PROXY_CONFIG_PATH, _FORGE_REGISTRY_PATH)
register_proxy_tools(mcp)
register_registry_tools(mcp)
register_diagnostics_tools(mcp)
register_governance_tools(mcp)
register_workspace_audit_tools(mcp)  # Round 43 P1: 6 维度全方位审计 MCP 暴露

from agora.server.tools_health import register_health_tools

register_health_tools(mcp)  # Phase 45: 健康自检 + 熵清理 + 债务自动种子

from agora.server.tools_registry_mcp import register_registry_mcp_tools

register_registry_mcp_tools(mcp)  # Phase 46: Agent Registry 暴露为 MCP 工具


async def _init_proxy():
    """Initialize the proxy manager and connect to all configured downstream services.

    Phase 1 — tries ``mcp_bootstrap.scan_and_launch()`` which internally calls
    ``proxy_manager.start()`` with full configs (command/args/cwd/init_timeout).
    If bootstrap succeeds, the second ``start()`` call is *skipped* to avoid
    disconnecting already-connected services.

    Phase 2 — syncs HTTP services from ``ServiceRegistry`` → ``ProxyRegistry``
    so that CLI-registered services appear in the proxy tool listing.

    Phase 3 — registers all proxy downstream tools as native FastMCP tools.
    """
    from agora.server.dependencies import (
        get_lifecycle_manager,
        get_proxy_manager,
        set_lifecycle_manager,
        set_proxy_manager,
    )

    pm = get_proxy_manager()
    if pm is not None:
        return

    # ── Phase 0 (BOS-ONLY): 立即裁剪非 BOS 工具，不等 proxy 初始化 ──
    if os.environ.get("AGORA_BOS_ONLY", "").lower() in ("1", "true", "yes"):
        await _bos_only_cleanup(mcp)
        logger.info("bos_only_mode: removed non-BOS management tools")

    pm = ProxyManager()
    set_proxy_manager(pm)
    set_lifecycle_manager(get_lifecycle_manager())

    # ── Phase 1: Try bootstrap (scan_and_launch internally calls start() with full configs) ──
    bootstrap_results = await mcp_bootstrap.scan_and_launch(pm)

    if not bootstrap_results:
        # No bootstrap available — load from proxy config file
        from agora.server.tools_proxy import (
            _load_proxy_services,  # type: ignore[import-not-found]
        )

        services = _load_proxy_services()
        if services:
            await pm.start(services)
    # else: scan_and_launch already connected services via _build_enabled_services + proxy_manager.start

    # ── Phase 2: Register HTTP services from ServiceRegistry ──
    from agora.server.tools_proxy import (
        _load_proxy_services,  # type: ignore[import-not-found]
    )

    proxy_configs = _load_proxy_services()
    await pm.registry.register_from_registry(registry, proxy_configs, lazy=True)

    # ── Phase 3: Register proxy tools ──
    from agora.server.tools_proxy import _register_proxy_tools

    _register_proxy_tools(mcp, pm)

    # ── Phase 4 (P45 W2): Seed BOSRouter from POC_SERVICES ──
    _bos_router.seed_from_poc(_POC_SERVICES)
    logger.info("bos_router_seeded", poc_count=_bos_router.count())

    # ── Phase 5.5 (FeatureGate): 加载 feature_groups + bos_domains ──
    from agora.mcp_proxy.feature_gate import FeatureGate

    gate = FeatureGate.get_instance()
    # 从代理配置文件预加载 feature_groups & bos_domains
    proxy_config_path = mcp_bootstrap.get_data_dir() / "agora-proxy-services.json"
    if proxy_config_path.exists():
        try:
            proxy_data = json.loads(proxy_config_path.read_text(encoding="utf-8"))
            gate.load(proxy_data)
            logger.info("feature_gate_initialized_from_proxy_config")
        except (json.JSONDecodeError, OSError):
            gate.load()
            logger.info("feature_gate_initialized_defaults")
    else:
        gate.load()
        logger.info("feature_gate_initialized_defaults")

    # ── Phase 6 (P46 W0): 配置 BOS 中间件 ──
    import yaml

    # 预种子路由表
    _bos_router.seed_from_poc(_POC_SERVICES)
    logger.info("bos_router: seeded from POC_SERVICES")

    rates_path = Path(__file__).parent.parent / "agora-bos-rates.yaml"
    if rates_path.exists():
        rates = yaml.safe_load(open(rates_path))
        for route in rates.get("routes", []):
            bos_rate_limiter.configure(route["prefix"], qps=route["qps"])
    else:
        # 硬编码回退
        bos_rate_limiter.configure("bos://analysis/minerva/", qps=5)
        bos_rate_limiter.configure("bos://analysis/code/", qps=10)
        bos_rate_limiter.configure("bos://memory/kronos/", qps=10)
        bos_rate_limiter.configure("bos://memory/kos/", qps=20)
    logger.info("bos_middleware_configured")

    # ── Phase 6 (P46 W1): 从 M1 Workflow 节点自动注册 BOS 路由 ──
    from agora.mcp.bos_auto_register import (
        auto_register_from_m1,  # type: ignore[import-not-found]
    )

    count = auto_register_from_m1()
    logger.info("auto_register_from_m1: %d workflow routes seeded", count)

    # ── Phase 7 (P47): 从 AGENTS.md 自动发现 + 信号热加载 ──
    from agora.mcp.bos_discovery import (
        discover_from_workspace,  # type: ignore[import-not-found]
    )

    discovered = discover_from_workspace()
    logger.info("bos_discovery: %d URIs discovered from AGENTS.md", discovered)
    _install_signal_handler()

    # ── Phase 8 (P48): 启动配置文件监听 ──
    rates_path = Path(__file__).parent.parent / "agora-bos-rates.yaml"
    if rates_path.exists():

        def _reload_rates():
            import yaml

            try:
                rates = yaml.safe_load(open(rates_path))
                for route in rates.get("routes", []):
                    bos_rate_limiter.configure(route["prefix"], qps=route["qps"])
                logger.info(
                    "config_watcher: rates reloaded (%d routes)",
                    len(rates.get("routes", [])),
                )
            except Exception as e:  # defensive fallback
                logger.error("config_watcher: reload failed: %s", e)

        config_watcher.file_path = str(rates_path)
        config_watcher._on_change = _reload_rates
        config_watcher.start(interval=5)
        logger.info("config_watcher: started")


async def _bos_only_cleanup(mcp_server: FastMCP) -> None:
    """移除所有非 BOS URI 相关的管理工具。

    BOS-only 模式下只保留:
      - BOS URI 解析 (resolve_bos_uri, read_resource, mutate_resource, ...)
      - BOS 资源 (bos://...)
      移除: proxy 基础设施、代理下游工具、路由/健康、管理噪声
    """
    # 只保留纯 BOS URI 工具
    KEEP_TOOLS = {
        "mutate_resource",
        "resolve_bos_uri",
        "read_resource",
        "list_bos_resources",
        "list_bos_domains",
        "get_bos_schema",
        "bos_middleware_status",
        "bos_reload_m1",
        "bos_reload_discovery",
        "bos_metrics_status",
        "watch_resource",
        "unwatch_resource",
        "list_bos_tools",
    }

    # 获取所有已注册工具
    try:
        provider = getattr(mcp_server, "_local_provider", None)
        if provider is None:
            return
        tools = await provider.list_tools()
    except Exception:  # defensive fallback
        return

    removed = 0
    for tool in tools:
        name = tool.name if hasattr(tool, "name") else str(tool)
        # 仅保留白名单中的 BOS URI 工具
        if name in KEEP_TOOLS:
            continue
        # 其余全部移除（含代理下游工具、proxy 基础设施、路由、管理工具）
        try:
            provider.remove_tool(name)
            removed += 1
        except (KeyError, Exception):  # defensive fallback
            pass

    if removed:
        logger.info("bos_only_cleanup: removed %d management tools", removed)


# ── 信号处理 (P46 W2) ─────────────────────────────────


def _install_signal_handler() -> None:
    """安装 SIGUSR1 信号处理器 — 热加载 BOS 配置。"""
    import signal

    import yaml

    def _reload_handler(signum, frame):
        logger.info("signal_handler: received SIGUSR1, reloading BOS config")
        rates_path = Path(__file__).parent.parent / "agora-bos-rates.yaml"
        if rates_path.exists():
            try:
                rates = yaml.safe_load(open(rates_path))
                for route in rates.get("routes", []):
                    bos_rate_limiter.configure(route["prefix"], qps=route["qps"])
                logger.info(
                    "signal_handler: rate limits reloaded (%d routes)",
                    len(rates.get("routes", [])),
                )
            except Exception as e:  # defensive fallback
                logger.error("signal_handler: failed to reload rates: %s", e)
        # Reload BOSRouter from POC_SERVICES
        for uri, svc in _POC_SERVICES.items():  # type: ignore[reportAttributeAccessIssue]
            _bos_router.register(
                uri,
                adapter="poc",
                config={
                    "domain": getattr(svc, "domain", ""),
                    "transport": getattr(svc, "transport", ""),
                },
            )
        logger.info(
            "signal_handler: BOSRouter reloaded (%d routes)", _bos_router.count()
        )

    try:
        signal.signal(signal.SIGUSR1, _reload_handler)
        logger.info(
            "signal_handler: SIGUSR1 handler installed (kill -USR1 %d to reload)",
            os.getpid(),
        )
    except (AttributeError, ValueError):
        pass  # Windows 不支持 SIGUSR1


# ── 信号处理 (P46 W2) ─────────────────────────────────


# ── Extracted Proxy Tools and Singletons to tools_proxy.py and dependencies.py ──


# ── Phase 34: Agora Mesh V2 (Agent Experience Layer) ────────────────


@mcp.resource("bos://agora/registry")
def agora_registry() -> str:
    """Introspection: returns a JSON dump of all registered tools and resources."""
    import json

    from agora.server.dependencies import get_proxy_manager

    pm = get_proxy_manager()
    if pm:
        tools = pm.registry.entries
        resources = pm.registry.resources if hasattr(pm.registry, "resources") else {}  # type: ignore[reportAttributeAccessIssue]
        return json.dumps(
            {
                "tools": [
                    {
                        "name": name,
                        "description": entry.description
                        if hasattr(entry, "description")
                        else str(entry),
                    }
                    for name, entry in tools.items()
                ],
                "resources": [
                    {"uri": uri, "name": res.name if hasattr(res, "name") else str(res)}
                    for uri, res in resources.items()
                ],
            },
            indent=2,
        )
    return json.dumps({"error": "proxy manager not initialized"})


@mcp.resource("bos://agora/status")
async def bos_agora_status() -> str:
    """BOS 系统内省 — 统一大盘: 路由/域/中间件/调用量.

    Agent 单次调用即可获取 BOS 系统全貌，无需调多个工具。
    """
    import json

    status = {
        "format_version": FORMAT_VERSION,
        "service": "agora",
        "router": {
            "total_routes": _bos_router.count(),
            "stats": _bos_router.stats(),
        },
        "middleware": {
            "rate_limiter": bos_rate_limiter.status(),
            "circuit_breaker": {
                "open_circuits": bos_circuit_breaker.status(),
            },
            "cache": bos_cache.status(),
        },
        "metrics": bos_metrics.summary(),
        "resources_total": _bos_router.count() + len(_POC_SERVICES),
    }
    return json.dumps(status, ensure_ascii=False, indent=2)


@mcp.resource("bos://{domain}/{package}/{action}")
async def bos_universal_resource(domain: str, package: str, action: str) -> str:
    """P45 W2: Universal BOS URI resource handler — 匹配所有 bos:// 请求。

    路由优先级: BOSRouter (POC) → ProxyManager (MCP 代理) → 404
    """
    import json

    from agora.server.dependencies import get_proxy_manager

    uri = f"bos://{domain}/{package}/{action}"
    # Step 1: BOSRouter
    route = _bos_router.resolve(uri)
    if route and route["adapter"] == "poc":
        try:
            result = await _resolve_bos_uri(uri)
            return json.dumps(
                {
                    "status": "ok",
                    "uri": uri,
                    "source": "bos_router",
                    "result": result,
                    "format_version": FORMAT_VERSION,
                }
            )
        except Exception as e:  # defensive fallback
            return json.dumps(
                {
                    "status": "error",
                    "uri": uri,
                    "error": str(e),
                    "format_version": FORMAT_VERSION,
                }
            )
    # Step 2: ProxyManager
    pm = get_proxy_manager()
    if pm:
        try:
            result = await pm.read_resource(uri)
            if isinstance(result, dict) and "contents" in result:
                return json.dumps(
                    {
                        "status": "ok",
                        "uri": uri,
                        "source": "proxy",
                        "contents": result["contents"],
                        "format_version": FORMAT_VERSION,
                    }
                )
        except Exception:  # defensive fallback
            pass
    # Step 3: Not found
    return json.dumps(
        {
            "status": "error",
            "uri": uri,
            "error": f"Resource not found or no provider for: {uri}",
            "format_version": FORMAT_VERSION,
        }
    )


# ── Service management tools ─────────────────────────────────────


# ═══════════════════════════════════════════════════════════════
# Section 6: API Key Tools (extracted → server/tools_api_keys.py)
# ═══════════════════════════════════════════════════════════════
from agora.server.tools_api_keys import register_tools as _register_api_keys

_register_api_keys(mcp, _ok, FORMAT_VERSION)


# ═══════════════════════════════════════════════════════════════
# Section: 执行引擎
# ═══════════════════════════════════════════════════════════════


@mcp.tool()
async def agora_execute(query: str, mode: str = "auto") -> dict:
    """Execute a natural language query by routing to the best matching MCP tool.

    Three modes:
    - direct: User knows the tool name ("docker list images" loads docker gateway)
    - recommend: User is unsure, system returns ranked recommendations
    - auto (default): Try direct → recommend → auto-discover external tools

    Args:
        query: Natural language description of what to do
        mode: Routing mode - 'direct', 'recommend', or 'auto' (default: auto)
    """
    try:
        from agora.server.dependencies import get_cached_router

        router_instance = get_cached_router()
        result = await router_instance.route(query, mode=mode)
        return _ok({"format_version": FORMAT_VERSION, **result})
    except Exception as e:  # defensive fallback
        logger.exception("agora_execute_failed", query=query, mode=mode)
        return _error(f"Execution failed: {e}")


@mcp.tool()
async def agora_capability_discover(
    status_filter: str = "",
    stale_days: float = 7.0,
) -> dict:
    """B3 discover 落地: 发现 agora 全部已注册能力 (BOS 路由 + B1/B2 能力治理)。

    返回 agora 能力生态全貌:
    - BOS 路由清单 (bos_router.list_all)
    - capability 有效状态 (capability_catalog.get: 含僵尸能力 deprecated 标记)
    - 使用统计汇总 (bos_metrics)
    - 僵尸能力候选 (report: active 但长期零调用)

    Args:
        status_filter: 按能力状态过滤 (active/deprecated/'' 全量)
        stale_days: 僵尸判定阈值 (默认 7 天)

    Returns:
        { total, active, deprecated, zombie_candidates, capabilities: [...] }
    """
    try:
        from agora.mcp.bos_router import bos_router as _br
        from agora.mcp.capability_catalog import capability_catalog as _cc

        # 1. BOS 路由清单
        routes = _br.list_all()
        route_uris = {r.get("prefix", "").rstrip("/") for r in routes}

        # 2. capability 有效状态 + 使用统计
        report = _cc.report(stale_days=stale_days)
        caps_raw = report.get("capabilities", {})
        caps: list[dict] = []
        active_count = 0
        deprecated_count = 0
        for uri, decl in sorted(caps_raw.items()):
            effective = _cc.get(uri, stale_days=stale_days) or decl
            status = effective.get("status", "active")
            if status_filter and status != status_filter:
                continue
            if status == "active":
                active_count += 1
            else:
                deprecated_count += 1
            entry = {
                "uri": uri,
                "status": status,
                "domain": decl.get("domain", ""),
                "package": decl.get("package", ""),
                "action": decl.get("action", ""),
                "description": decl.get("description", "")[:120],
                "routed": uri in route_uris or any(
                    uri.startswith(r) for r in route_uris
                ),
                "calls": decl.get("calls", 0),
                "stale_days": decl.get("usage", {}).get("stale_days"),
                "zombie": bool(effective.get("zombie")),
            }
            caps.append(entry)

        return _ok(
            {
                "format_version": FORMAT_VERSION,
                "total": len(caps),
                "active": active_count,
                "deprecated": deprecated_count,
                "zombie_candidates": report.get("stale_candidates", []),
                "routes_total": len(routes),
                "capabilities": caps,
            }
        )
    except Exception as e:  # defensive fallback
        logger.exception("agora_capability_discover_failed")
        return _error(f"Discovery failed: {e}")


def main():
    """Start the Agora MCP server. Default: stdio. Use --sse for SSE mode."""
    import argparse

    parser = argparse.ArgumentParser(description="Agora MCP Server")
    parser.add_argument(
        "--sse", action="store_true", help="Start in SSE mode (port 7431)"
    )
    parser.add_argument(
        "--http",
        action="store_true",
        help="Start in HTTP mode (port AGORA_MCP_HTTP_PORT)",
    )
    args = parser.parse_args()

    if args.sse:
        sse_main()
    elif args.http:
        http_main()
    else:
        sys.stderr.write("Agora MCP Server (stdio) starting...\n")
        mcp.run()


# HTTP / SSE 入口 (P110 拆分, mcp_entry.py). TASK-F7114ABA 治本.
from agora.server.mcp_entry import http_main, sse_main

if __name__ == "__main__":
    main()

# Re-exports for test imports
from agora.server.tools_proxy import proxy_call, proxy_remove_service, proxy_status
from agora.server.tools_registry import route_call
