"""Audit/Governance/A2A MCP tools — extracted from server/mcp.py (God Module Phase 1).

Provides tools for audit queries, push notifications, A2A task management,
and agent card discovery.
"""

from __future__ import annotations

import json
import os

import structlog
from fastmcp import FastMCP

from agora.core.service_base import is_safe_url  # type: ignore[import-not-found]
from agora.plugins.identity.agent_card import (
    service_to_agent_card,  # type: ignore[import-not-found]
)
from agora.server._response import FORMAT_VERSION, _error, _ok

logger = structlog.get_logger(__name__)


def _get_registry():
    """Lazy-import ServiceRegistry from mcp.py."""
    from agora.server.mcp import registry  # type: ignore[import-not-found]

    return registry


def _get_bus():
    """Lazy-import EventBus from mcp.py."""
    from agora.server.mcp import _bus  # type: ignore[import-not-found]

    return _bus


def _get_auditor():
    """Lazy-import AuditSubscriber from mcp.py."""
    from agora.server.mcp import _auditor  # type: ignore[import-not-found]

    return _auditor


def _get_proxy_manager():
    """Lazy-import ProxyManager from dependencies.py."""
    from agora.server.dependencies import get_proxy_manager

    return get_proxy_manager()


def _get_task_manager():
    """Lazy-init and return the global TaskManager from mcp.py."""
    from agora.server.mcp import _get_task_manager  # type: ignore[import-not-found]

    return _get_task_manager()


# ── A2A Convergence Helper (ADR-0300) ──────────────────────────────


def _resolve_convergence_meta(
    tool_name: str, run_id: str = "", bos_uri: str = ""
) -> dict[str, str]:
    """Derive OMO Agent Workflow Run-ID and BOS 5-domain convergence metadata (ADR-0300)."""
    resolved_run_id = (
        run_id
        or os.environ.get("AGCP_RUN_ID", "")
        or os.environ.get("OMO_WORKFLOW_RUN_ID", "")
    )
    resolved_uri = bos_uri
    if not resolved_uri and tool_name:
        parts = tool_name.split(".", 1)
        pkg = parts[0] if parts else "unknown"
        action = parts[1] if len(parts) > 1 else "execute"
        domain_map = {
            "kems": "memory",
            "kos": "memory",
            "eidos": "memory",
            "minerva": "analysis",
            "codeanalyze": "analysis",
            "iris": "analysis",
            "ontoderive": "analysis",
            "metaos": "governance",
            "omo": "governance",
            "cockpit": "capability",
            "aetherforge": "compute",
        }
        dom = domain_map.get(pkg, "capability")
        resolved_uri = f"bos://{dom}/{pkg}/{action}"

    domain = "capability"
    if resolved_uri.startswith("bos://"):
        segments = resolved_uri[len("bos://") :].split("/", 1)
        if segments:
            domain = segments[0]

    return {
        "run_id": resolved_run_id,
        "bos_uri": resolved_uri,
        "domain": domain,
        "adr_policy": "ADR-0300",
    }


# ── Agent Card helpers ──────────────────────────────────────────────


def _get_proxy_tools(service_name: str) -> list[dict]:
    """Collect proxy tool descriptions for a service.

    Returns list of tool dicts with name/description/inputSchema keys,
    or empty list if proxy manager is not initialized or has no matching tools.
    """
    pm = _get_proxy_manager()
    if not pm:
        return []
    tools = []
    for entry in pm.registry.entries.values():
        if entry.service_name == service_name:
            tools.append(
                {
                    "name": entry.original_name,
                    "description": entry.description,
                    "inputSchema": entry.parameters,
                }
            )
    return tools


def _build_agent_card(service_name: str) -> tuple[dict | None, str | None]:
    """Build an A2A Agent Card dict for a registered service.

    Returns (card_dict, None) on success, or (None, error_message) on failure.
    """
    registry = _get_registry()
    svc = registry.get(service_name)
    if not svc:
        return None, f"Service '{service_name}' not found"
    try:
        tools = _get_proxy_tools(service_name)
        tags = (
            svc.tags
            if isinstance(svc.tags, list)
            else (svc.tags.split(",") if svc.tags else [])
        )

        # Check if authentication is configured
        from agora.governance import KeyManager  # type: ignore[import-not-found]

        has_auth = KeyManager().has_keys()

        card = service_to_agent_card(
            name=svc.name,
            description=svc.description,
            protocol=svc.protocol,
            mcp_endpoint=svc.mcp_endpoint,
            port=svc.port,
            tags=tags,
            tools=tools if tools else None,
            has_auth=has_auth,
            has_push_notifications=_get_bus().has_push_subscribers(),
            has_state_transitions=bool(registry.get_transitions(limit=1)),
            provider_info={"organization": "Agora Hub"},
            documentation_url="https://github.com/starlink-awaken/agora",
        )
        return card.to_dict(), None
    except Exception as e:  # defensive fallback
        return None, str(e)


# ═══════════════════════════════════════════════════════════════
# Tool Registration
# ═══════════════════════════════════════════════════════════════


def register_governance_tools(mcp: FastMCP) -> None:
    """Register all audit/governance/A2A MCP tools."""

    # ── audit_query ───────────────────────────────────────────────

    @mcp.tool()
    def audit_query(
        actor: str = "",
        resource: str = "",
        event_type: str = "",
        since: str = "",
        limit: int = 50,
    ) -> dict:
        """Query the audit log for persisted events.

        Use this for debugging, compliance checks, and understanding
        what has happened in the system over time.

        Args:
            actor: Filter by actor (e.g., 'registry', 'pipeline', 'proxy', 'system')
            resource: Filter by resource type (e.g., 'service', 'route', 'proxy', 'system')
            event_type: Filter by event type pattern (e.g., 'registry:*', 'error:*')
            since: ISO timestamp (e.g., '2026-05-01T00:00:00Z')
            limit: Max results (default 50)

        Returns filtered audit log entries with metadata.
        """
        auditor = _get_auditor()
        entries = auditor.query(
            actor=actor,
            resource=resource,
            event_type=event_type,
            since=since,
            limit=limit,
        )
        return _ok(
            {
                "format_version": FORMAT_VERSION,
                "entries": entries,
                "count": len(entries),
            }
        )

    # ── audit_stats ─────────────────────────────────────────────────

    @mcp.tool()
    def audit_stats(since: str = "") -> dict:
        """Get audit log statistics — counts grouped by risk level and event type.

        Args:
            since: ISO timestamp to filter from (e.g., '2026-05-01T00:00:00Z')

        Returns summary stats useful for dashboards and monitoring.
        """
        auditor = _get_auditor()
        stats = auditor.stats(since=since)
        return _ok(
            {
                "format_version": FORMAT_VERSION,
                "stats": stats,
            }
        )

    # ── register_push_notification ─────────────────────────────────

    @mcp.tool()
    def register_push_notification(callback_url: str, event_types: str = "*") -> dict:
        """Register a webhook callback for push notification delivery.

        When matching events occur, Agora will POST the event payload
        to the specified callback URL (with retry up to 3 attempts).

        Args:
            callback_url: HTTP endpoint to receive push notifications
            event_types: Comma-separated event type patterns
                         (e.g. 'registry:*,route:call.failed' or '*' for all)
        """
        if not callback_url or not callback_url.startswith("http"):
            return _error("callback_url must be a valid HTTP URL")
        if not is_safe_url(callback_url):
            return _error(f"Unsafe callback URL: {callback_url}")

        patterns = [p.strip() for p in event_types.split(",") if p.strip()]

        bus = _get_bus()
        results = {}
        for pattern in patterns:
            sub_id = bus.subscribe("a2a-push", pattern, callback_url)
            results[pattern] = sub_id

        return _ok(
            {
                "format_version": FORMAT_VERSION,
                "subscriptions": results,
                "callback_url": callback_url,
            }
        )

    # ── a2a_send_task ──────────────────────────────────────────────

    @mcp.tool()
    async def a2a_send_task(
        tool_name: str,
        arguments: str = "{}",
        session_id: str = "",
        run_id: str = "",
        bos_uri: str = "",
    ) -> dict:
        """Submit a tool call as an A2A task and execute it with OMO convergence metadata (ADR-0300).

        Creates a task, routes it to the appropriate service via the router,
        and returns the completed result with task metadata and convergence bridge info.

        Args:
            tool_name: Full tool name (e.g. 'minerva.research_now')
            arguments: JSON string of tool arguments
            session_id: Optional session identifier for grouping related tasks
            run_id: Optional OMO Agent Workflow run identifier for task convergence
            bos_uri: Optional BOS URI mapping for 5-domain convergence
        """
        try:
            args = json.loads(arguments) if isinstance(arguments, str) else arguments
        except json.JSONDecodeError:
            args = {}

        tm = _get_task_manager()
        task = tm.create_task("", tool_name, args, session_id)  # type: ignore[reportCallIssue]
        result = await tm.execute_task(task.id)  # type: ignore[reportAttributeAccessIssue]
        if result is None:
            return _error("Task execution returned no result")

        convergence_meta = _resolve_convergence_meta(tool_name, run_id, bos_uri)
        result_dict = result.to_dict()
        if convergence_meta["run_id"]:
            result_dict["run_id"] = convergence_meta["run_id"]
        result_dict["bos_uri"] = convergence_meta["bos_uri"]

        return _ok(
            {
                "format_version": FORMAT_VERSION,
                "task": result_dict,
                "convergence_meta": convergence_meta,
            }
        )

    # ── a2a_get_task ───────────────────────────────────────────────

    @mcp.tool()
    def a2a_get_task(task_id: str) -> dict:
        """Get an A2A task's current status and result.

        Args:
            task_id: The task ID to query
        """
        tm = _get_task_manager()
        task = tm.get_task(task_id)
        if task is None:
            return _error(f"Task '{task_id}' not found")

        return _ok(
            {
                "format_version": FORMAT_VERSION,
                "task": task.to_dict(),  # type: ignore[reportAttributeAccessIssue]
            }
        )

    # ── a2a_cancel_task ────────────────────────────────────────────

    @mcp.tool()
    def a2a_cancel_task(task_id: str) -> dict:
        """Cancel a submitted or in-progress A2A task.

        Only tasks in 'submitted' or 'working' state can be canceled.

        Args:
            task_id: The task ID to cancel
        """
        tm = _get_task_manager()
        if tm.cancel_task(task_id):
            task = tm.get_task(task_id)
            return _ok(
                {
                    "format_version": FORMAT_VERSION,
                    "action": "canceled",
                    "task_id": task_id,
                    "task": task.to_dict() if task else None,  # type: ignore[reportAttributeAccessIssue]
                }
            )
        else:
            return _error(f"Task '{task_id}' not found or already completed")

    # ── a2a_list_tasks ─────────────────────────────────────────────

    @mcp.tool()
    def a2a_list_tasks(
        service: str = "", status: str = "", since: str = "", limit: int = 50
    ) -> dict:
        """List A2A tasks with optional filters.

        Args:
            service: Filter by service name (empty returns all)
            status: Filter by status — submitted | working | completed | failed | canceled (empty returns all)
            since: ISO timestamp lower bound (e.g. '2026-05-01T00:00:00Z')
            limit: Max results (default 50)
        """
        tm = _get_task_manager()
        tasks = tm.list_tasks(service=service, status=status, since=since, limit=limit)  # type: ignore[reportAttributeAccessIssue]
        return _ok(
            {
                "format_version": FORMAT_VERSION,
                "tasks": [t.to_dict() for t in tasks],
                "count": len(tasks),
            }
        )

    # ── list_agent_cards ───────────────────────────────────────────

    @mcp.tool()
    def list_agent_cards() -> dict:
        """List all registered Agent Cards — A2A-compatible agent metadata.

        Returns a mapping of service name → Agent Card for every registered
        service, including basic identity, capabilities, and skills.

        Use this tool when you (or another agent) need to discover what
        agents/services are available through the Agora hub.
        """
        registry = _get_registry()
        services = registry.list_all()
        cards = {}
        for svc in services:
            card, err = _build_agent_card(svc.name)
            cards[svc.name] = card if card else {"error": err}

        return _ok(
            {
                "format_version": FORMAT_VERSION,
                "agent_cards": cards,
                "count": len(cards),
            }
        )

    # ── get_agent_card ─────────────────────────────────────────────

    @mcp.tool()
    def get_agent_card(name: str) -> dict:
        """Get the Agent Card for a specific service.

        Args:
            name: Service name (e.g., 'minerva', 'kos', 'sophia')

        Returns a single A2A-compatible Agent Card with identity, capabilities,
        and skills for the requested service.
        """
        card, err = _build_agent_card(name)
        if card is None:
            return _error(err or "Failed to build Agent Card")
        return _ok(
            {
                "format_version": FORMAT_VERSION,
                "agent_card": card,
            }
        )
