"""Dashboard data provider — generate JSON for health dashboard with service topology."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass
class ServiceCard:
    """Per-service health card with current metrics.

    Attributes:
        name: Service name.
        status: One of ``"healthy"``, ``"degraded"``, ``"unhealthy"``, ``"unknown"``.
        uptime_pct: Current uptime percentage (0-100).
        p99_latency_ms: 99th percentile latency in milliseconds.
        error_rate: Error rate as a fraction (0-1).
        last_checked: Unix timestamp of last health check.
    """

    name: str
    status: str = "unknown"
    uptime_pct: float = 0.0
    p99_latency_ms: float = 0.0
    error_rate: float = 0.0
    last_checked: float = field(default_factory=time.time)


@dataclass
class TopologyEdge:
    """A directed edge in the service dependency graph.

    Attributes:
        source: Upstream/caller service name.
        target: Downstream/callee service name.
        call_count: Total calls observed.
        avg_latency_ms: Average call latency.
        p99_latency_ms: P99 call latency.
        error_rate: Fraction of calls that errored.
    """

    source: str
    target: str
    call_count: int = 0
    avg_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0
    error_rate: float = 0.0


@dataclass
class DashboardConfig:
    """Configuration for the dashboard data provider.

    Attributes:
        title: Dashboard title.
        refresh_interval_sec: Suggested refresh interval.
        degrade_p99_threshold_ms: P99 above this → degraded.
        degrade_error_threshold: Error rate above this → degraded.
        unhealthy_p99_threshold_ms: P99 above this → unhealthy.
        unhealthy_error_threshold: Error rate above this → unhealthy.
    """

    title: str = "Health Dashboard"
    refresh_interval_sec: int = 30
    degrade_p99_threshold_ms: float = 500.0
    degrade_error_threshold: float = 0.01  # 1%
    unhealthy_p99_threshold_ms: float = 2000.0
    unhealthy_error_threshold: float = 0.05  # 5%


class DashboardData:
    """Generate dashboard data for health monitoring, including per-service cards,
    overall summary, and a service dependency topology for visualization.

    Maintains backward compatibility with the existing stub API (``update_service``,
    ``add_edge``, ``get_overview``, ``get_service_detail``) while adding configurable
    health assessment, topology graph data, and structured dashboard JSON output.

    Typical usage::

        db = DashboardData()
        db.update_service("api-gateway", status="healthy", uptime_pct=99.95, p99_ms=120, error_rate=0.001)
        db.add_edge("web", "api-gateway", call_count=5000, avg_ms=25.0, p99_ms=80.0)
        overview = db.get_overview()
        print(db.to_json())
    """

    def __init__(self, config: DashboardConfig | None = None) -> None:
        self.config = config or DashboardConfig()
        self._services: dict[str, ServiceCard] = {}
        self._edges: list[TopologyEdge] = []
        self._generated_at: float = 0.0

    # ------------------------------------------------------------------
    # Backward-compatible API
    # ------------------------------------------------------------------

    def update_service(
        self,
        name: str,
        status: str = "healthy",
        uptime_pct: float = 100.0,
        p99_ms: float = 0.0,
        error_rate: float = 0.0,
    ) -> None:
        """Update or create a service health card.

        If *status* is not provided explicitly, it is auto-derived from the
        metric thresholds in :class:`DashboardConfig`.
        """
        if status == "healthy" and self.config:
            status = self._derive_status(p99_ms, error_rate)
        self._services[name] = ServiceCard(
            name=name,
            status=status,
            uptime_pct=uptime_pct,
            p99_latency_ms=p99_ms,
            error_rate=error_rate,
            last_checked=time.time(),
        )

    def add_edge(
        self,
        source: str,
        target: str,
        call_count: int = 0,
        avg_ms: float = 0.0,
        p99_ms: float = 0.0,
        error_rate: float = 0.0,
    ) -> None:
        """Add or update a topology edge between two services.

        If an edge from *source* to *target* already exists, its metrics are
        updated.
        """
        for edge in self._edges:
            if edge.source == source and edge.target == target:
                edge.call_count = call_count
                edge.avg_latency_ms = avg_ms
                edge.p99_latency_ms = p99_ms
                edge.error_rate = error_rate
                return
        self._edges.append(
            TopologyEdge(
                source=source,
                target=target,
                call_count=call_count,
                avg_latency_ms=avg_ms,
                p99_latency_ms=p99_ms,
                error_rate=error_rate,
            )
        )

    def get_overview(self) -> dict:
        """Return the full dashboard overview as a dict.

        Includes service cards, summary, topology graph, and metadata.
        """
        cards = list(self._services.values())
        healthy = sum(1 for c in cards if c.status == "healthy")
        degraded = sum(1 for c in cards if c.status == "degraded")
        unhealthy = sum(1 for c in cards if c.status == "unhealthy")
        total = len(cards)

        self._generated_at = time.time()

        return {
            "dashboard": {
                "title": self.config.title,
                "generated_at": datetime.fromtimestamp(self._generated_at, tz=UTC).isoformat(),
                "refresh_interval_sec": self.config.refresh_interval_sec,
            },
            "services": [
                {
                    "name": c.name,
                    "status": c.status,
                    "uptime_pct": c.uptime_pct,
                    "p99_ms": c.p99_latency_ms,
                    "error_rate": c.error_rate,
                }
                for c in cards
            ],
            "summary": {
                "total": total,
                "healthy": healthy,
                "degraded": degraded,
                "unhealthy": unhealthy,
                "health_pct": round(healthy / total * 100, 2) if total else 100.0,
            },
            "topology": [
                {
                    "source": e.source,
                    "target": e.target,
                    "calls": e.call_count,
                    "avg_ms": e.avg_latency_ms,
                    "p99_ms": e.p99_latency_ms,
                    "error_rate": e.error_rate,
                }
                for e in self._edges
            ],
            "updated_at": self._generated_at,
        }

    def get_service_detail(self, name: str) -> dict | None:
        """Return detailed information for a specific service, or None if unknown."""
        card = self._services.get(name)
        if not card:
            return None

        # Find related edges (both upstream and downstream)
        upstream = [
            {
                "peer": e.source,
                "calls": e.call_count,
                "avg_ms": e.avg_latency_ms,
                "p99_ms": e.p99_latency_ms,
                "error_rate": e.error_rate,
                "direction": "upstream",
            }
            for e in self._edges
            if e.target == name
        ]
        downstream = [
            {
                "peer": e.target,
                "calls": e.call_count,
                "avg_ms": e.avg_latency_ms,
                "p99_ms": e.p99_latency_ms,
                "error_rate": e.error_rate,
                "direction": "downstream",
            }
            for e in self._edges
            if e.source == name
        ]

        return {
            "service": {"name": card.name, "status": card.status},
            "metrics": {
                "uptime_pct": card.uptime_pct,
                "p99_ms": card.p99_latency_ms,
                "error_rate": card.error_rate,
            },
            "connections": upstream + downstream,
            "dependency_count": {
                "upstream": len(upstream),
                "downstream": len(downstream),
            },
        }

    # ------------------------------------------------------------------
    # Extended API
    # ------------------------------------------------------------------

    def remove_service(self, name: str) -> bool:
        """Remove a service card. Returns True if it existed."""
        removed = self._services.pop(name, None) is not None
        # Also remove edges involving this service
        before = len(self._edges)
        self._edges = [e for e in self._edges if e.source != name and e.target != name]
        return removed or len(self._edges) < before

    def remove_edge(self, source: str, target: str) -> bool:
        """Remove a specific topology edge. Returns True if it existed."""
        before = len(self._edges)
        self._edges = [e for e in self._edges if not (e.source == source and e.target == target)]
        return len(self._edges) < before

    def get_topology_data(self) -> dict[str, Any]:
        """Return topology as a graph representation suitable for visualization.

        Returns nodes and edges in a format compatible with common graph frameworks.
        """
        # Collect unique nodes
        node_set: set[str] = set(self._services.keys())
        for e in self._edges:
            node_set.add(e.source)
            node_set.add(e.target)

        nodes = [
            {
                "id": n,
                "status": self._services[n].status if n in self._services else "unknown",
                "group": self._derive_group(n),
            }
            for n in sorted(node_set)
        ]

        links = [
            {
                "source": e.source,
                "target": e.target,
                "value": e.call_count,
                "avg_ms": e.avg_latency_ms,
                "p99_ms": e.p99_latency_ms,
                "error_rate": e.error_rate,
            }
            for e in self._edges
        ]

        return {"nodes": nodes, "links": links}

    def get_health_summary(self) -> dict[str, Any]:
        """Return a compact health summary suitable for status badges."""
        cards = list(self._services.values())
        if not cards:
            return {"overall": "no_data", "services": 0, "issues": []}

        unhealthy = [c for c in cards if c.status == "unhealthy"]
        degraded = [c for c in cards if c.status == "degraded"]
        healthy = [c for c in cards if c.status == "healthy"]

        if unhealthy:
            overall = "unhealthy"
        elif degraded:
            overall = "degraded"
        elif healthy:
            overall = "healthy"
        else:
            overall = "unknown"

        issues = []
        for c in unhealthy + degraded:
            reason = []
            if c.p99_latency_ms > self.config.unhealthy_p99_threshold_ms:
                reason.append(f"high_p99={c.p99_latency_ms:.1f}ms")
            if c.error_rate > self.config.unhealthy_error_threshold:
                reason.append(f"high_error_rate={c.error_rate:.4f}")
            issues.append({"service": c.name, "status": c.status, "reasons": reason})

        return {
            "overall": overall,
            "services": len(cards),
            "healthy": len(healthy),
            "degraded": len(degraded),
            "unhealthy": len(unhealthy),
            "issues": issues,
        }

    def to_json(self, pretty: bool = False) -> str:
        """Export the full dashboard as a JSON string.

        Args:
            pretty: If True, use indented formatting.
        """
        import json

        data = self.get_overview()
        if pretty:
            return json.dumps(data, indent=2, ensure_ascii=False, default=str)
        return json.dumps(data, ensure_ascii=False, default=str)

    def reset(self) -> None:
        """Clear all services and edges."""
        self._services.clear()
        self._edges.clear()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _derive_status(self, p99_ms: float, error_rate: float) -> str:
        """Derive a status label from metric thresholds."""
        cfg = self.config
        if p99_ms > cfg.unhealthy_p99_threshold_ms or error_rate > cfg.unhealthy_error_threshold:
            return "unhealthy"
        if p99_ms > cfg.degrade_p99_threshold_ms or error_rate > cfg.degrade_error_threshold:
            return "degraded"
        return "healthy"

    @staticmethod
    def _derive_group(service_name: str) -> str:
        """Derive a visualization group from the service name.

        Heuristic: prefix-based grouping (e.g., 'api-*' → 'API layer').
        """
        prefixes: dict[str, str] = {
            "api-": "API Layer",
            "db-": "Database",
            "cache-": "Cache",
            "mq-": "Message Queue",
            "worker-": "Workers",
            "web-": "Frontend",
            "auth-": "Authentication",
            "gateway-": "Gateway",
        }
        for prefix, group in prefixes.items():
            if service_name.startswith(prefix):
                return group
        return "Other"
