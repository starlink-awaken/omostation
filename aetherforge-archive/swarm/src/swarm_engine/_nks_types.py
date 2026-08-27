"""Type definitions and helpers extracted from nks_task_planner.py (ARCH-003 SRP refactor).

Includes enums, dataclasses, protocols, and pure utility functions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol, TypedDict

# ── Enums ──────────────────────────────────────────────────────────────────


class ExecutionStrategy(Enum):
    """Execution strategy for a planned task."""

    PARALLEL = "parallel"
    SEQUENTIAL = "sequential"
    CAREFUL = "careful"


# ── Risk helpers ───────────────────────────────────────────────────────────

_RISK_THRESHOLDS = [
    (0.2, "MINIMAL"),
    (0.4, "LOW"),
    (0.6, "MEDIUM"),
    (0.8, "HIGH"),
]


def get_risk_level(score: float) -> str:
    for threshold, level in _RISK_THRESHOLDS:
        if score < threshold:
            return level
    return "CRITICAL"


# ── Dataclasses ────────────────────────────────────────────────────────────


@dataclass
class TaskAnalysis:
    """Result of analysing a planned task against the NKS knowledge graph."""

    risk_score: float = 0.0
    affected_components: list[str] = field(default_factory=list)
    test_files: list[str] = field(default_factory=list)
    execution_strategy: str = ExecutionStrategy.SEQUENTIAL.value
    suggested_agents: list = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    impact_report: Any = None
    related_code: list[str] = field(default_factory=list)
    requires_approval: bool = False

    def _get_risk_level(self) -> str:
        return get_risk_level(self.risk_score)

    def to_dict(self) -> dict[str, Any]:
        return {
            "risk_score": self.risk_score,
            "risk_level": self._get_risk_level(),
            "affected_components": self.affected_components,
            "test_files": self.test_files,
            "execution_strategy": self.execution_strategy,
            "requires_approval": self.requires_approval,
            "suggested_agents": self.suggested_agents,
            "related_code": self.related_code,
            "metadata": self.metadata,
        }


@dataclass
class AgentContext:
    """Context bundle provided to an agent before it begins work on a task."""

    architecture_overview: str = ""
    affected_files: list[str] = field(default_factory=list)
    risk_assessment: dict[str, Any] = field(default_factory=dict)
    suggested_tools: list = field(default_factory=list)
    call_graphs: dict[str, Any] = field(default_factory=dict)
    related_entities: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "architecture_overview": self.architecture_overview,
            "affected_files": self.affected_files,
            "risk_assessment": self.risk_assessment,
            "suggested_tools": self.suggested_tools,
            "call_graphs": self.call_graphs,
            "related_entities": self.related_entities,
            "metadata": self.metadata,
        }


# ── Protocols ─────────────────────────────────────────────────────────────


class ImpactReportLike(Protocol):
    risk_score: float
    suggested_tests: list[str]


class ImpactAnalyzerLike(Protocol):
    graph_store: Any

    def analyze_file_change(self, file_path: str, change_type: str) -> ImpactReportLike: ...


class QueryEngineLike(Protocol):
    def query_related_code(self, file_path: str, depth: int = 2) -> list[str]: ...
    def query_entities_by_file(self, file_path: str) -> list[object]: ...
    def query_call_graph(self, entity_id: str, depth: int = 2) -> Any: ...
    def get_neighbors(self, entity_id: str) -> list[Any]: ...


# ── TypedDict ──────────────────────────────────────────────────────────────


class AnalyzeTaskParams(TypedDict, total=False):
    task_description: str
    modified_files: list[str]
    change_type: str


# ── Utility ────────────────────────────────────────────────────────────────


def require_str_list(value: Any, field_name: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise TypeError(f"{field_name} must be list[str]")
    return value
