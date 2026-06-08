"""Task decomposition into sub-tasks with dependency analysis and topological ordering.

Maps to TS source: agentmesh/packages/engine/src/decomposer.ts

Provides:
  - Decomposer: strategy-based project decomposition
  - Dependency graph construction, validation, cycle detection
  - Topological sort (Kahn's algorithm) for execution batching
  - Archetype strategies in decomposer_strategies.py
"""

from __future__ import annotations

import time as _time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from runtime.executor.decomposer_strategies import STRATEGIES

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------


class ProjectArchetype(StrEnum):
    SOFTWARE_DEV = "software-dev"
    CREATIVE_WRITING = "creative-writing"
    VISUAL_PRODUCTION = "visual-production"
    DOCUMENT_PROCESSING = "document-processing"
    CUSTOM = "custom"


class ComplexityLevel(StrEnum):
    SIMPLE = "simple"
    STANDARD = "standard"
    ADVANCED = "advanced"


@dataclass
class SubProject:
    id: str
    name: str
    description: str
    archetype: ProjectArchetype = ProjectArchetype.CUSTOM
    goals: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    estimated_complexity: ComplexityLevel = ComplexityLevel.STANDARD
    priority: int = 5
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class DecompositionResult:
    original_project: str
    archetype: ProjectArchetype
    sub_projects: list[SubProject]
    dependency_graph: list[DependencyEdge]
    execution_batches: list[list[str]]
    estimated_parallelism: int
    decomposition_strategy: str
    created_at: float = 0.0


@dataclass
class DependencyEdge:
    from_id: str
    to_id: str
    edge_type: str = "hard"


@dataclass
class ValidationResult:
    valid: bool
    errors: list[str] = field(default_factory=list)


@dataclass
class ProjectConfig:
    name: str
    description: str = ""
    archetype: ProjectArchetype = ProjectArchetype.CUSTOM
    goals: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    complexity: ComplexityLevel = ComplexityLevel.STANDARD


# ---------------------------------------------------------------------------
# Decomposer
# ---------------------------------------------------------------------------


class Decomposer:
    """Decomposes project configs into dependency-ordered sub-projects."""

    def __init__(self) -> None:
        self._strategies: dict[ProjectArchetype, Any] = dict(STRATEGIES)

    def register_strategy(self, archetype: ProjectArchetype, strategy: Any) -> None:
        self._strategies[archetype] = strategy

    def get_strategy(self, archetype: ProjectArchetype) -> Any | None:
        return self._strategies.get(archetype)

    def decompose(self, config: ProjectConfig) -> DecompositionResult:
        strategy = self._strategies.get(config.archetype)
        if strategy is None:
            msg = f"No decomposition strategy registered for archetype: {config.archetype}"
            raise ValueError(msg)

        sub_projects = strategy(config)
        dep_graph = self._build_dependency_graph(sub_projects)
        validation = self._validate_dependencies(sub_projects)
        if not validation.valid:
            msg = "Dependency validation failed:\n  - " + "\n  - ".join(validation.errors)
            raise ValueError(msg)

        batches = self._topological_sort(sub_projects, dep_graph)
        return DecompositionResult(
            original_project=config.name,
            archetype=config.archetype,
            sub_projects=sub_projects,
            dependency_graph=dep_graph,
            execution_batches=batches,
            estimated_parallelism=self._estimate_parallelism(batches),
            decomposition_strategy=config.archetype.value,
            created_at=_time.time(),
        )

    @staticmethod
    def _build_dependency_graph(sub_projects: list[SubProject]) -> list[DependencyEdge]:
        return [
            DependencyEdge(from_id=sp.id, to_id=dep)
            for sp in sub_projects
            for dep in sp.dependencies
        ]

    def _validate_dependencies(self, sub_projects: list[SubProject]) -> ValidationResult:
        errors: list[str] = []
        id_set = {sp.id for sp in sub_projects}

        for sp in sub_projects:
            for dep_id in sp.dependencies:
                if dep_id not in id_set:
                    errors.append(f'Sub-project "{sp.name}" ({sp.id}) references unknown dependency: {dep_id}')
                if dep_id == sp.id:
                    errors.append(f'Sub-project "{sp.name}" ({sp.id}) depends on itself')

        if not errors:
            cycle_msg = self._detect_cycles(sub_projects)
            if cycle_msg:
                errors.append(cycle_msg)

        return ValidationResult(valid=len(errors) == 0, errors=errors)

    @staticmethod
    def _topological_sort(sub_projects: list[SubProject], edges: list[DependencyEdge]) -> list[list[str]]:
        ids = {sp.id for sp in sub_projects}
        name_map = {sp.id: sp.name for sp in sub_projects}
        in_degree: dict[str, int] = {iid: 0 for iid in ids}
        dependents: dict[str, list[str]] = {iid: [] for iid in ids}

        for edge in edges:
            if edge.edge_type != "hard":
                continue
            in_degree[edge.from_id] = in_degree.get(edge.from_id, 0) + 1
            dependents.setdefault(edge.to_id, []).append(edge.from_id)

        priority_map = {sp.id: sp.priority for sp in sub_projects}
        batches: list[list[str]] = []
        current = sorted(
            [iid for iid in ids if in_degree.get(iid, 0) == 0],
            key=lambda x: -priority_map.get(x, 0),
        )

        while current:
            batches.append(list(current))
            for mid in current:
                for dep in dependents.get(mid, []):
                    in_degree[dep] -= 1
            current = sorted(
                [did for did in ids if in_degree.get(did, 0) == 0 and not any(did in b for b in batches)],
                key=lambda x: -priority_map.get(x, 0),
            )

        remaining = [iid for iid in ids if in_degree.get(iid, 0) > 0]
        if remaining:
            names = [name_map.get(iid, iid) for iid in remaining]
            raise ValueError(f"Cycle detected in dependency graph involving: {', '.join(names)}")
        return batches

    @staticmethod
    def _detect_cycles(sub_projects: list[SubProject]) -> str | None:
        name_map = {sp.id: sp.name for sp in sub_projects}
        adjacency = {sp.id: list(sp.dependencies) for sp in sub_projects}
        color: dict[str, int] = {sp.id: 0 for sp in sub_projects}

        for sp in sub_projects:
            if color[sp.id] != 0:
                continue
            stack: list[tuple[str, int]] = [(sp.id, 0)]
            color[sp.id] = 1
            while stack:
                node_id, idx = stack[-1]
                neighbors = adjacency.get(node_id, [])
                if idx >= len(neighbors):
                    color[node_id] = 2
                    stack.pop()
                    continue
                stack[-1] = (node_id, idx + 1)
                neighbor = neighbors[idx]
                nc = color.get(neighbor, 0)
                if nc == 1:
                    path = " -> ".join(name_map.get(nid, nid) for nid, _ in stack)
                    return f"Cycle detected: {path} -> {name_map.get(neighbor, neighbor)}"
                if nc == 0:
                    color[neighbor] = 1
                    stack.append((neighbor, 0))
        return None

    @staticmethod
    def _estimate_parallelism(batches: list[list[str]]) -> int:
        return max((len(b) for b in batches), default=0)


def create_decomposer() -> Decomposer:
    """Create a Decomposer with all default strategies."""
    return Decomposer()
