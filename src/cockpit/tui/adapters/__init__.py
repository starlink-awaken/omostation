"""TUI Domain Adapters — bridging domain state into USP v1 SurfaceEnvelopes."""

from __future__ import annotations

from typing import Any

from cockpit.surface.cards import (
    ActionButton,
    ActionPanelCard,
    DagEdge,
    DagGraphCard,
    DagNode,
    DataTableCard,
    LogEntry,
    LogStreamCard,
    MetricCell,
    MetricGridCard,
    TableColumn,
)
from cockpit.surface.protocol import (
    CardType,
    RefreshMode,
    SurfaceDomain,
    SurfaceEnvelope,
)


class BaseDomainAdapter:
    """Base adapter producing USP v1 envelopes for a domain."""

    domain: SurfaceDomain = SurfaceDomain.UNKNOWN

    def get_summary_card(self) -> SurfaceEnvelope:
        raise NotImplementedError

    def get_detail_cards(self) -> list[SurfaceEnvelope]:
        return []


class GovernanceAdapter(BaseDomainAdapter):
    domain = SurfaceDomain.GOVERNANCE

    def get_summary_card(self) -> SurfaceEnvelope:
        card = MetricGridCard(
            cells=[
                MetricCell(label="GaC Gates", value="56/56", unit="pass", trend="up"),
                MetricCell(label="ADRs", value=451, unit="docs", trend="neutral"),
                MetricCell(label="Compliance", value=100.0, unit="%", trend="up"),
                MetricCell(label="Active Bets", value=1, unit="in-flight", trend="neutral"),
            ],
            columns=4,
        )
        return SurfaceEnvelope(
            domain=self.domain,
            card_type=CardType.METRIC_GRID,
            title="🛡️ Governance & Compliance Health",
            payload=card.to_dict(),
            refresh_mode=RefreshMode.POLL,
        )

    def get_detail_cards(self) -> list[SurfaceEnvelope]:
        table = DataTableCard(
            columns=[
                TableColumn(key="id", label="Check ID", width=25),
                TableColumn(key="status", label="Status", width=10),
                TableColumn(key="category", label="Category", width=15),
                TableColumn(key="description", label="Description"),
            ],
            rows=[
                {
                    "id": "sfop-slots",
                    "status": "PASS",
                    "category": "architecture",
                    "description": "DFSQ/SFOP single-S slot validation",
                },
                {
                    "id": "execution-chain",
                    "status": "PASS",
                    "category": "execution",
                    "description": "End-to-end execution chain validation",
                },
                {
                    "id": "adr-coverage",
                    "status": "PASS",
                    "category": "ssot",
                    "description": "ADR numbering and frontmatter integrity",
                },
                {
                    "id": "change-lane-check",
                    "status": "PASS",
                    "category": "gate",
                    "description": "Git index change lane separation",
                },
            ],
            total_rows=4,
        )
        actions = ActionPanelCard(
            actions=[
                ActionButton(
                    id="run_gate", label="Run Gate", variant="primary", payload={"cmd": "make gac-local-gate"}
                ),
                ActionButton(id="audit", label="Full Audit", variant="secondary", payload={"cmd": "make omo-audit"}),
            ],
            title="Governance Actions",
        )
        return [
            SurfaceEnvelope(
                domain=self.domain, card_type=CardType.DATA_TABLE, title="Gate Conformance", payload=table.to_dict()
            ),
            SurfaceEnvelope(
                domain=self.domain, card_type=CardType.ACTION_PANEL, title="Actions", payload=actions.to_dict()
            ),
        ]


class AgentAdapter(BaseDomainAdapter):
    """Fused Multi-Agent Swarm view (formerly swarm_app.py)."""

    domain = SurfaceDomain.AGENT

    def get_summary_card(self) -> SurfaceEnvelope:
        card = MetricGridCard(
            cells=[
                MetricCell(label="Active Swarm", value=1, unit="nodes", trend="neutral"),
                MetricCell(label="Running Tasks", value=1, unit="tasks", trend="up"),
                MetricCell(label="Channel Traffic", value="0.8k", unit="msg/m", trend="up"),
                MetricCell(label="A2A Handshakes", value=100.0, unit="%", trend="neutral"),
            ],
            columns=4,
        )
        return SurfaceEnvelope(
            domain=self.domain,
            card_type=CardType.METRIC_GRID,
            title="🤖 Swarm Fleet & Agent Runtime",
            payload=card.to_dict(),
            refresh_mode=RefreshMode.STREAM,
        )

    def get_detail_cards(self) -> list[SurfaceEnvelope]:
        dag = DagGraphCard(
            nodes=[
                DagNode(id="orchestrator", label="Sovereign Orchestrator", status="running"),
                DagNode(id="governance_worker", label="Governance Agent", status="running"),
                DagNode(id="researcher", label="Codebase Researcher", status="done"),
            ],
            edges=[
                DagEdge(source="orchestrator", target="governance_worker", label="dispatch"),
                DagEdge(source="governance_worker", target="researcher", label="query"),
            ],
            layout="LR",
            highlight=["governance_worker"],
        )
        return [
            SurfaceEnvelope(
                domain=self.domain,
                card_type=CardType.DAG_GRAPH,
                title="Swarm Delegation Topology",
                payload=dag.to_dict(),
            ),
        ]


class ComputeAdapter(BaseDomainAdapter):
    """Fused Sovereign Compute view (formerly compute_hud.py)."""

    domain = SurfaceDomain.COMPUTE

    def get_summary_card(self) -> SurfaceEnvelope:
        card = MetricGridCard(
            cells=[
                MetricCell(label="Local VRAM", value="18.2 / 64", unit="GB", trend="neutral"),
                MetricCell(label="Fabric Nodes", value=1, unit="omlxc", trend="neutral"),
                MetricCell(label="TTFT Latency", value="0.0", unit="ms (warm)", trend="up"),
                MetricCell(label="KV Cache Hit", value=98.4, unit="%", trend="up"),
            ],
            columns=4,
        )
        return SurfaceEnvelope(
            domain=self.domain,
            card_type=CardType.METRIC_GRID,
            title="⚡ Sovereign Compute Mesh & VRAM Heatmap",
            payload=card.to_dict(),
            refresh_mode=RefreshMode.POLL,
        )


class GenericAdapter(BaseDomainAdapter):
    def __init__(self, domain_name: str) -> None:
        try:
            self.domain = SurfaceDomain(domain_name)
        except ValueError:
            self.domain = SurfaceDomain.UNKNOWN
        self._name = domain_name

    def get_summary_card(self) -> SurfaceEnvelope:
        card = MetricGridCard(
            cells=[
                MetricCell(label="Domain", value=self._name.capitalize()),
                MetricCell(label="Status", value="READY"),
                MetricCell(label="Envelope", value="USP v1"),
            ],
            columns=3,
        )
        return SurfaceEnvelope(
            domain=self.domain,
            card_type=CardType.METRIC_GRID,
            title=f"📦 {self._name.capitalize()} Domain Overview",
            payload=card.to_dict(),
        )


ADAPTER_MAP: dict[str, BaseDomainAdapter] = {
    "governance": GovernanceAdapter(),
    "agent": AgentAdapter(),
    "compute": ComputeAdapter(),
}


def get_adapter(domain_name: str) -> BaseDomainAdapter:
    """Get adapter for domain with automatic fallback."""
    return ADAPTER_MAP.get(domain_name) or GenericAdapter(domain_name)
