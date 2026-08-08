"""Capability health projection for Workflow Mesh admission gates."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any


def _value(item: Any, key: str, default: Any = None) -> Any:
    if isinstance(item, dict):
        return item.get(key, default)
    return getattr(item, key, default)


def _health(item: Any) -> str:
    value = _value(item, "health", _value(item, "status", "green"))
    if value in {"active", "alive", "healthy", "green"}:
        return "green"
    if value in {"yellow", "degraded", "stale"}:
        return "yellow"
    return "red"


def build_capability_health_snapshot(
    required_capabilities: Iterable[str],
    *,
    agents: Iterable[Any] = (),
    nodes: Iterable[Any] = (),
    services: Iterable[Any] = (),
    backends: dict[str, Any] | None = None,
    observed_at: str | None = None,
) -> dict[str, Any]:
    """Project independent worker/service signals into an admission snapshot.

    The projection is intentionally read-only. It reports availability and
    evidence sources, while OMO remains the authority that admits a workflow.
    """
    required = list(dict.fromkeys(str(item) for item in required_capabilities))
    candidates: dict[str, list[dict[str, Any]]] = {item: [] for item in required}

    for agent in agents:
        capabilities = _value(agent, "capabilities", []) or []
        for capability in required:
            if capability in capabilities:
                candidates[capability].append(
                    {
                        "source": "agent",
                        "id": _value(agent, "agent_id", "unknown"),
                        "health": _health(agent),
                    }
                )

    for node in nodes:
        capabilities = _value(node, "capabilities", {}) or {}
        bos_uris = _value(node, "bos_uris", []) or []
        for capability in required:
            declared = capability in capabilities or any(
                capability in str(uri) for uri in bos_uris
            )
            if declared:
                candidates[capability].append(
                    {
                        "source": "swarm_node",
                        "id": _value(node, "node_id", "unknown"),
                        "health": _health(node),
                    }
                )

    for service in services:
        name = str(_value(service, "name", "unknown"))
        declared = _value(service, "capabilities", []) or []
        tags = _value(service, "tags", []) or []
        for capability in required:
            if capability in declared or capability in tags or capability == name:
                candidates[capability].append(
                    {
                        "source": "service",
                        "id": name,
                        "health": _health(service),
                    }
                )

    for name, backend in (backends or {}).items():
        for capability in required:
            if capability == name or capability in str(
                _value(backend, "capability", "")
            ):
                candidates[capability].append(
                    {
                        "source": "backend",
                        "id": name,
                        "health": "green" if _value(backend, "alive", False) else "red",
                    }
                )

    projected: dict[str, dict[str, Any]] = {}
    for capability, sources in candidates.items():
        healthy = [item for item in sources if item["health"] != "red"]
        best = (
            "green"
            if any(item["health"] == "green" for item in sources)
            else ("yellow" if healthy else "red")
        )
        projected[capability] = {
            "available": bool(healthy),
            "health": best,
            "sources": sources,
        }

    available = all(item["available"] for item in projected.values())
    all_green = all(item["health"] == "green" for item in projected.values())
    status = (
        "healthy"
        if available and all_green
        else ("degraded" if available else "unhealthy")
    )
    return {
        "status": status,
        "observed_at": observed_at or datetime.now(UTC).isoformat(),
        "source": "agora.workflow_health",
        "required_capabilities": required,
        "capabilities": projected,
    }


__all__ = ["build_capability_health_snapshot"]
