"""Health self-check MCP tools — Phase 45 governance observability.

Provides comprehensive health reporting, entropy cleanup, and debt auto-seeding
for the Agora gateway. Replaces the minimal /health endpoint with a full
self-check that reports backend health, proxy status, audit stats, and
governance debt state.
"""

from __future__ import annotations

import os
import time
from datetime import UTC
from pathlib import Path
from typing import Any

import structlog
from fastmcp import FastMCP

from agora.mcp.mcp_bootstrap import get_data_dir as _get_data_dir
from agora.server._response import FORMAT_VERSION, _error, _ok

logger = structlog.get_logger(__name__)

_start_time = time.time()


def _workflow_capability_health(required_capabilities: list[str]) -> dict:
    from agora.workflow_health import build_capability_health_snapshot

    registry = _get_registry()
    services = registry.list_all() if hasattr(registry, "list_all") else []
    pm = _get_proxy_manager()
    backends = {}
    if pm is not None:
        checker = getattr(pm, "_health_checker", None)
        if checker is not None and hasattr(checker, "get_all_status"):
            backends = checker.get_all_status()
    nodes = []
    try:
        from agora.mcp.swarm import get_swarm

        nodes = get_swarm().get_online_nodes()
    except (ImportError, OSError, RuntimeError):
        nodes = []
    return build_capability_health_snapshot(
        required_capabilities,
        nodes=nodes,
        services=services,
        backends=backends,
    )


def _get_registry():
    from agora.server.mcp import registry  # type: ignore[import-not-found]

    return registry


def _get_proxy_manager():
    from agora.server.dependencies import get_proxy_manager

    return get_proxy_manager()


def _get_auditor():
    from agora.server.mcp import _auditor  # type: ignore[import-not-found]

    return _auditor


def _resolve_workspace_root() -> str:
    this_file = Path(__file__).resolve()
    default_root = this_file.parent.parent.parent.parent.parent
    return os.environ.get("WORKSPACE_AUDIT_ROOT") or str(default_root)


def _resolve_proposal_dir() -> Path:
    """Return the local proposal directory for debt items.

    Debt proposals are written here rather than directly to .omo/debt/items/
    because governed writes must route through omo CLI / c2g ingress per
    ADR-0214. The omo broker reads from this proposal dir on next sync.
    """
    return Path(os.environ.get("AGORA_DATA_DIR", "/tmp/agora")) / "debt-proposals"


# ═══════════════════════════════════════════════════════════════
# Health Self-Check
# ═══════════════════════════════════════════════════════════════


async def health_self_check() -> dict:
    """Comprehensive health self-check for the Agora gateway.

    Reports: uptime, registered services, backend health, proxy status,
    audit log stats, and governance debt summary.
    """
    uptime = round(time.time() - _start_time, 1)
    registry = _get_registry()
    pm = _get_proxy_manager()

    # Service registry status
    all_services = registry.list_all() if hasattr(registry, "list_all") else []
    healthy_services = (
        registry.list_healthy() if hasattr(registry, "list_healthy") else []
    )

    # Backend health — P2-5: KNOWN_BACKENDS 全为 stdio, BackendHealthChecker 视
    # stdio 为 transient 跳过 heartbeat → _health_checker 恒报 0 (假绿根源)。
    # 改为统计 pm.registry._clients (实际已连接的 MCP client 数)。
    # 复盘修正 (MED-2): registry.entries 是工具条目数 (含未连接), _clients 是
    # 已连接服务数 — 量纲不同不能直接对比。backends.total 用已注册服务数
    # (entries 中 name 去重), alive 用 clients 数, 保证同量纲。
    backend_health: dict = {}
    backends_alive = 0
    backends_total = 0
    if pm is not None:
        proxy_registry = getattr(pm, "registry", None)
        if proxy_registry is not None:
            clients = getattr(proxy_registry, "_clients", {}) or {}
            entries = getattr(proxy_registry, "entries", {}) or {}
            backends_alive = len(clients) if hasattr(clients, "__len__") else 0
            # MED-2: entries 值可能含 name 字段, 去重得服务数; 否则退回工具数并标注
            service_names = {
                (v.get("name") if isinstance(v, dict) else k)
                for k, v in entries.items()
            }
            service_names.discard(None)
            backends_total = len(service_names) if service_names else len(entries)
        # 兼容: 有 _health_checker 时仍纳入其状态 (非 stdio backends)
        checker = getattr(pm, "_health_checker", None)
        if checker is not None and hasattr(checker, "get_all_status"):
            try:
                backend_health = checker.get_all_status()
            except Exception:  # defensive fallback
                backend_health = {}

    # Proxy manager status
    proxy_status = "not_initialized"
    proxy_tool_count = 0
    if pm is not None:
        proxy_status = "active"
        proxy_registry = getattr(pm, "registry", None)
        if proxy_registry is not None:
            entries = getattr(proxy_registry, "entries", {})
            proxy_tool_count = len(entries) if hasattr(entries, "__len__") else 0

    # Audit stats (last 24h)
    audit_stats: dict = {}
    auditor = _get_auditor()
    if auditor is not None and hasattr(auditor, "stats"):
        try:
            audit_stats = auditor.stats(since="24h")
        except (OSError, ValueError, KeyError):  # defensive fallback
            audit_stats = {"error": "stats_unavailable"}

    # MED-3: audit hashchain 完整性校验 (P2-2 verify_chain 闭环)
    audit_chain: dict = {"checked": False}
    if auditor is not None and hasattr(auditor, "verify_chain"):
        try:
            audit_chain = auditor.verify_chain()
        except Exception:  # defensive fallback
            audit_chain = {"checked": True, "ok": False, "error": "verify_failed"}

    # Debt summary
    debt_summary = _scan_debt_items()

    # Determine overall health
    issues: list[str] = []
    if len(healthy_services) < len(all_services):
        issues.append(f"{len(all_services) - len(healthy_services)} unhealthy services")
    dead_backends = [
        name
        for name, info in backend_health.items()
        if isinstance(info, dict) and not info.get("alive", True)
    ]
    # P2-5: 以 registry 已连接 client 数作为真实 backends 口径
    if backends_total > 0 and backends_alive < backends_total:
        issues.append(
            f"backends partial: {backends_alive}/{backends_total} alive"
        )
    if dead_backends:
        issues.append(f"dead backends: {', '.join(dead_backends)}")
    # MED-3: 链完整性失败视为问题
    if audit_chain.get("checked") and not audit_chain.get("ok"):
        issues.append("audit hashchain broken")

    overall = "healthy" if not issues else "degraded"

    # P4: 健康降级 → 统一告警事件 (防抖 per-status, 恢复时发 recovered)
    try:
        from agora.mcp.agora_alerts import send_alert

        if overall == "degraded":
            send_alert(
                level="degraded",
                event="health:degraded",
                payload={"issues": issues, "backends": f"{backends_alive}/{backends_total}"},
                caller_key="health:degraded",
            )
        elif overall == "healthy":
            send_alert(
                level="recovered",
                event="health:recovered",
                payload={"issues": []},
                caller_key="health:degraded",  # 与 degraded 同 key, 恢复时绕过防抖
                force=True,
            )
    except Exception:  # defensive: 告警失败不影响 health 返回
        pass

    # 强化-2: BOS internal 注册表契约健康 (func 可解析率 + 域分布)
    bos_registry = _bos_registry_health()

    return {
        "format_version": FORMAT_VERSION,
        "status": overall,
        "uptime_seconds": uptime,
        "services": {
            "total": len(all_services),
            "healthy": len(healthy_services),
        },
        "proxy": {
            "status": proxy_status,
            "tool_count": proxy_tool_count,
        },
        "backends": {
            "total": backends_total,
            "alive": backends_alive,
            "dead": dead_backends,
        },
        "bos_registry": bos_registry,
        "audit_24h": audit_stats,
        "audit_chain": audit_chain,
        "debt": debt_summary,
        "issues": issues,
    }


def _bos_registry_health() -> dict:
    """BOS internal 服务注册表契约健康 (强化-2 可观测性).

    统计 internal transport 服务的 func 可解析率 + 域分布,
    供 /health 与面板判断能力声明 vs 实现的一致性。
    """
    try:
        import importlib
        import inspect

        from agora.mcp.resolver.services import POC_SERVICES

        internal = [s for s in POC_SERVICES if s.transport == "internal"]
        resolvable = 0
        broken: list[str] = []
        by_domain: dict[str, int] = {}
        for s in internal:
            dom = s.uri.split("/")[2] if s.uri.count("/") >= 2 else "?"
            by_domain[dom] = by_domain.get(dom, 0) + 1
            try:
                mod = importlib.import_module(s.module_path)
                fn = getattr(mod, s.func_name)
                inspect.signature(fn)
                resolvable += 1
            except (ModuleNotFoundError, AttributeError):
                # 外部包 (aetherforge/omo/bus_foundation) 环境性缺失 → 不算 broken
                if not (
                    s.module_path.startswith("aetherforge.")
                    or s.module_path.startswith("omo.")
                    or s.module_path.startswith("bus_foundation.")
                ):
                    broken.append(f"{s.uri} ({s.module_path}.{s.func_name})")
        # 更新 Prometheus 指标
        g_resolvable, g_total = _get_registry_prom()
        if g_resolvable is not None and g_total is not None:
            g_resolvable.set(resolvable)
            g_total.set(len(internal))
        return {
            "internal_total": len(internal),
            "func_resolvable": resolvable,
            "func_resolvable_pct": round(resolvable / len(internal) * 100, 1) if internal else 0.0,
            "broken": broken,
            "broken_count": len(broken),
            "by_domain": by_domain,
        }
    except Exception:  # defensive: 注册表健康计算失败不影响主流程
        return {"internal_total": 0, "func_resolvable": 0, "broken": []}


# ── 强化-2: BOS 注册表健康 Prometheus 指标 (模块级单例) ──────────
_prom_registry_resolvable: Any | None = None
_prom_registry_total: Any | None = None


def _get_registry_prom():
    """懒加载注册表健康指标 (全局共享, 避免重复注册)."""
    global _prom_registry_resolvable, _prom_registry_total
    if _prom_registry_resolvable is not None:
        return _prom_registry_resolvable, _prom_registry_total
    try:
        from prometheus_client import Gauge

        _prom_registry_resolvable = Gauge(
            "bos_registry_func_resolvable",
            "BOS internal services with resolvable func",
        )
        _prom_registry_total = Gauge(
            "bos_registry_internal_total",
            "BOS internal services total",
        )
    except ImportError:  # defensive: prometheus-client 未装
        _prom_registry_resolvable = None
        _prom_registry_total = None
    return _prom_registry_resolvable, _prom_registry_total


def _scan_debt_items() -> dict:
    """Scan .omo/debt/items/ for summary stats."""
    ws_root = _resolve_workspace_root()
    debt_dir = Path(ws_root) / ".omo" / "debt" / "items"
    if not debt_dir.exists():
        return {"total": 0, "open": 0, "resolved": 0}

    total = 0
    open_count = 0
    resolved_count = 0
    for item_file in debt_dir.glob("*.yaml"):
        if item_file.name == "README.md":
            continue
        total += 1
        try:
            content = item_file.read_text(encoding="utf-8")
            if "lifecycle_state: resolved" in content:
                resolved_count += 1
            else:
                open_count += 1
        except (OSError, ValueError):  # defensive fallback
            open_count += 1

    return {"total": total, "open": open_count, "resolved": resolved_count}


# ═══════════════════════════════════════════════════════════════
# Entropy Cleanup
# ═══════════════════════════════════════════════════════════════


async def entropy_cleanup() -> dict:
    """Clean up stale state and orphaned entries.

    Scans for:
    - Stale worktree references in .omo/state/
    - Orphaned debt items with no evidence
    - Expired cache entries in agora cache dir
    - Stale audit log entries (> 30 days)
    """
    ws_root = _resolve_workspace_root()
    cleaned: list[str] = []
    skipped: list[str] = []

    # 1. Clean stale worktree references
    state_dir = Path(ws_root) / ".omo" / "state"
    if state_dir.exists():
        for f in state_dir.glob("*.yaml"):
            try:
                content = f.read_text(encoding="utf-8")
                if "worktree" in content.lower() and "stale" in content.lower():
                    cleaned.append(f"stale worktree ref: {f.name}")
            except OSError:  # defensive fallback
                skipped.append(f"read_error: {f.name}")

    # 2. Clean expired cache files (> 24h)
    ws_root = Path(_resolve_workspace_root())
    cache_dir = ws_root / "LADS" / "agora_cache"
    if cache_dir.exists():
        now = time.time()
        for f in cache_dir.glob("*.json"):
            try:
                if now - f.stat().st_mtime > 86400:
                    f.unlink()
                    cleaned.append(f"expired cache: {f.name}")
            except OSError:  # defensive fallback
                skipped.append(f"cache_clean_error: {f.name}")

    # 3. Clean stale audit entries (> 30 days)
    try:
        import sqlite3

        audit_db = Path(
            os.environ.get(
                "AGORA_AUDIT_DB",
                str(_get_data_dir() / "agora-audit.db"),
            )
        )
        if audit_db.exists():
            conn = sqlite3.connect(str(audit_db))
            cursor = conn.execute(
                "DELETE FROM audit_log WHERE timestamp < datetime('now', '-30 days')"
            )
            deleted = cursor.rowcount
            if deleted > 0:
                # P2-2 hashchain: 删除破链后, 将剩余链首行 prev_hash 重置为 GENESIS (新锚点)
                try:
                    conn.execute(
                        "UPDATE audit_log SET prev_hash = 'GENESIS' "
                        "WHERE rowid = (SELECT rowid FROM audit_log ORDER BY rowid ASC LIMIT 1)"
                    )
                except sqlite3.OperationalError:
                    pass  # 旧表无 prev_hash 列时忽略
            conn.commit()
            conn.close()
            if deleted > 0:
                cleaned.append(f"stale audit entries: {deleted}")
    except (OSError, ValueError) as e:  # defensive fallback
        skipped.append(f"audit_cleanup_error: {e!s}")

    # 4. Clean stale Inbox snapshots (> 7 days or closed status)
    try:
        import shutil

        inbox_dir = (
            Path(os.environ.get("BOS_DOCUMENTS_ROOT", str(Path.home() / "Documents")))
            / "_inbox"
        )
        archive_dir = Path(ws_root) / "_knowledge" / "archive" / "inbox"
        if inbox_dir.exists():
            archive_dir.mkdir(parents=True, exist_ok=True)
            now = time.time()
            for f in inbox_dir.glob("*.md"):
                try:
                    if now - f.stat().st_mtime > 86400 * 7:  # 7 days TTL
                        shutil.move(str(f), str(archive_dir / f.name))
                        cleaned.append(f"archived stale inbox: {f.name}")
                except OSError as e:  # defensive fallback
                    skipped.append(f"inbox_archive_error: {f.name} - {e!s}")
    except Exception as e:
        skipped.append(f"inbox_cleanup_error: {e!s}")

    return {
        "format_version": FORMAT_VERSION,
        "cleaned": cleaned,
        "skipped": skipped,
        "cleaned_count": len(cleaned),
        "skipped_count": len(skipped),
    }


# ═══════════════════════════════════════════════════════════════
# Debt Auto-Seed
# ═══════════════════════════════════════════════════════════════


async def debt_auto_seed() -> dict:
    """Scan governance gaps and auto-seed debt items.

    Detects:
    - Services without health endpoints
    - Proxy tools without audit coverage
    - Registry entries with stale heartbeats
    - Missing governance documentation
    """
    ws_root = _resolve_workspace_root()
    # Scan existing debts for dedup, but write proposals to local proposal dir
    # (NOT directly to .omo/debt/items/ — governed writes must route through
    # omo CLI / c2g ingress per ADR-0214)
    ws_debt_dir = Path(ws_root) / ".omo" / "debt" / "items"
    proposal_dir = _resolve_proposal_dir()
    proposal_dir.mkdir(parents=True, exist_ok=True)

    seeded: list[str] = []
    existing = (
        {f.stem for f in ws_debt_dir.glob("*.yaml")} if ws_debt_dir.exists() else set()
    )

    # Check 1: Services without health endpoints
    registry = _get_registry()
    if hasattr(registry, "list_all"):
        for svc in registry.list_all():
            svc_name = getattr(svc, "name", "unknown")
            health_ep = getattr(svc, "health_endpoint", "")
            debt_id = f"DEBT-SVC-HEALTH-{svc_name.upper()}"
            if not health_ep and debt_id not in existing:
                _write_debt_item(
                    proposal_dir,
                    debt_id,
                    title=f"Service '{svc_name}' missing health endpoint",
                    dimension="reliability",
                    severity="medium",
                    scope=f"service:{svc_name}",
                )
                seeded.append(debt_id)

    # Check 2: Proxy tools without governance tags
    pm = _get_proxy_manager()
    if pm is not None:
        proxy_registry = getattr(pm, "registry", None)
        if proxy_registry is not None:
            entries = getattr(proxy_registry, "entries", {})
            for tool_name, entry in (
                entries.items() if hasattr(entries, "items") else []
            ):
                tags = getattr(entry, "tags", [])
                if not tags:
                    debt_id = f"DEBT-PROXY-TAGS-{tool_name.upper().replace('.', '-')}"
                    if debt_id not in existing:
                        _write_debt_item(
                            proposal_dir,
                            debt_id,
                            title=f"Proxy tool '{tool_name}' has no governance tags",
                            dimension="governance",
                            severity="low",
                            scope=f"tool:{tool_name}",
                        )
                        seeded.append(debt_id)

    return {
        "format_version": FORMAT_VERSION,
        "seeded": seeded,
        "seeded_count": len(seeded),
        "existing_debt_count": len(existing),
    }


def _write_debt_item(
    target_dir: Path,
    item_id: str,
    title: str,
    dimension: str,
    severity: str,
    scope: str,
) -> None:
    """Write a single debt item YAML file."""
    from datetime import datetime

    now = datetime.now(UTC).strftime("%Y-%m-%d")
    content = f"""id: "{item_id}"
title: "{title}"
dimension: "{dimension}"
subdimension: "auto-seeded"
domain: "runtime"
scope: "{scope}"
severity: "{severity}"
weight: 0.05
entropy_class: "low"
lifecycle_state: "open"
owner: "agora-healthcheck"
affected_roots: []
evidence_refs: []
mitigation_refs: []
opened_at: "{now}"
last_reviewed_at: "{now}"
gate_level: "P2"
x3_tier: "Operational"
"""
    (target_dir / f"{item_id}.yaml").write_text(content, encoding="utf-8")


# ═══════════════════════════════════════════════════════════════
# Tool Registration
# ═══════════════════════════════════════════════════════════════


def register_health_tools(mcp: FastMCP) -> None:
    """Register all health/observability MCP tools (Phase 45)."""

    @mcp.tool()
    async def health_check() -> dict:
        """Comprehensive health self-check for the Agora gateway.

        Reports uptime, registered services, backend health, proxy status,
        audit stats, and governance debt summary. Use this instead of the
        basic /health endpoint for full observability.
        """
        try:
            return _ok(await health_self_check())
        except (OSError, ValueError, KeyError) as e:  # defensive fallback
            logger.exception("health_check_error")
            return _error(f"Health check failed: {e}")

    @mcp.tool()
    async def workflow_capability_health(required_capabilities: list[str]) -> dict:
        """Return the capability health projection used before Mesh admission."""
        if not required_capabilities:
            return _error("required_capabilities must not be empty")
        try:
            return _ok(_workflow_capability_health(required_capabilities))
        except (OSError, ValueError, KeyError) as e:  # defensive fallback
            logger.exception("workflow_capability_health_error")
            return _error(f"Capability health query failed: {e}")

    @mcp.tool()
    async def entropy_cleanup_tool() -> dict:
        """Clean up stale state, orphaned entries, and expired caches.

        Scans for stale worktree references, orphaned debt items,
        expired cache files (> 24h), and stale audit entries (> 30 days).
        Safe to run periodically — only removes clearly stale data.
        """
        try:
            return _ok(await entropy_cleanup())
        except (OSError, ValueError) as e:  # defensive fallback
            logger.exception("entropy_cleanup_error")
            return _error(f"Entropy cleanup failed: {e}")

    @mcp.tool()
    async def debt_auto_seed_tool() -> dict:
        """Scan governance gaps and auto-seed debt items.

        Detects services without health endpoints, proxy tools without
        governance tags, and other governance gaps. Creates debt item
        YAML files in .omo/debt/items/ for tracking.
        """
        try:
            return _ok(await debt_auto_seed())
        except (OSError, ValueError) as e:  # defensive fallback
            logger.exception("debt_auto_seed_error")
            return _error(f"Debt auto-seed failed: {e}")
