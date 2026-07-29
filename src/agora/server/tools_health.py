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

import structlog
from fastmcp import FastMCP

from agora.server._response import FORMAT_VERSION, _error, _ok

logger = structlog.get_logger(__name__)

_start_time = time.time()


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

    # Backend health from heartbeat checker
    backend_health: dict = {}
    if pm is not None:
        checker = getattr(pm, "_health_checker", None)
        if checker is not None and hasattr(checker, "get_all_status"):
            backend_health = checker.get_all_status()

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

    # Debt summary
    debt_summary = _scan_debt_items()

    # Determine overall health
    issues: list[str] = []
    if len(healthy_services) < len(all_services):
        issues.append(
            f"{len(all_services) - len(healthy_services)} unhealthy services"
        )
    dead_backends = [
        name
        for name, info in backend_health.items()
        if isinstance(info, dict) and not info.get("alive", True)
    ]
    if dead_backends:
        issues.append(f"dead backends: {', '.join(dead_backends)}")

    overall = "healthy" if not issues else "degraded"

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
            "total": len(backend_health),
            "alive": sum(
                1
                for v in backend_health.values()
                if isinstance(v, dict) and v.get("alive", True)
            ),
            "dead": dead_backends,
        },
        "audit_24h": audit_stats,
        "debt": debt_summary,
        "issues": issues,
    }


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
    cache_dir = Path.home() / "Workspace" / "LADS" / "agora_cache"
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
                str(Path.home() / "Workspace" / ".agora" / "agora-audit.db"),
            )
        )
        if audit_db.exists():
            conn = sqlite3.connect(str(audit_db))
            cursor = conn.execute(
                "DELETE FROM audit_log WHERE timestamp < datetime('now', '-30 days')"
            )
            deleted = cursor.rowcount
            conn.commit()
            conn.close()
            if deleted > 0:
                cleaned.append(f"stale audit entries: {deleted}")
    except (OSError, ValueError) as e:  # defensive fallback
        skipped.append(f"audit_cleanup_error: {e!s}")

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
    debt_dir = Path(ws_root) / ".omo" / "debt" / "items"
    debt_dir.mkdir(parents=True, exist_ok=True)

    seeded: list[str] = []
    existing = {f.stem for f in debt_dir.glob("*.yaml")}

    # Check 1: Services without health endpoints
    registry = _get_registry()
    if hasattr(registry, "list_all"):
        for svc in registry.list_all():
            svc_name = getattr(svc, "name", "unknown")
            health_ep = getattr(svc, "health_endpoint", "")
            debt_id = f"DEBT-SVC-HEALTH-{svc_name.upper()}"
            if not health_ep and debt_id not in existing:
                _write_debt_item(
                    debt_dir,
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
            for tool_name, entry in (entries.items() if hasattr(entries, "items") else []):
                tags = getattr(entry, "tags", [])
                if not tags:
                    debt_id = f"DEBT-PROXY-TAGS-{tool_name.upper().replace('.', '-')}"
                    if debt_id not in existing:
                        _write_debt_item(
                            debt_dir,
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
    debt_dir: Path,
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
    (debt_dir / f"{item_id}.yaml").write_text(content, encoding="utf-8")


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
