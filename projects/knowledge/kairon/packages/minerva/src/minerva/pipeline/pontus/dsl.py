"""Pipeline DSL — YAML-based pipeline definition and validation."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class StepDef:
    """A single step in a pipeline."""

    id: str
    action: str
    depends_on: list[str] = field(default_factory=list)
    params: dict[str, Any] = field(default_factory=dict)


@dataclass
class PipelineDef:
    """Top-level pipeline definition."""

    name: str
    steps: list[StepDef] = field(default_factory=list)


def load_pipeline(yaml_path: str) -> PipelineDef:
    """Load a pipeline definition from a YAML file.

    Expected YAML structure:
        name: my-pipeline
        steps:
          - id: step1
            action: fetch
            params:
              url: https://example.com
          - id: step2
            action: transform
            depends_on: [step1]
    """
    path = Path(yaml_path)
    if not path.exists():
        raise FileNotFoundError(f"Pipeline file not found: {yaml_path}")

    with open(path) as f:
        raw = yaml.safe_load(f)

    if not isinstance(raw, dict):
        raise ValueError("Pipeline YAML must be a mapping at the top level")

    name = raw.get("name", path.stem)
    steps_data = raw.get("steps", [])

    if not isinstance(steps_data, list):
        raise ValueError("'steps' must be a list")

    steps = []
    for i, sd in enumerate(steps_data):
        if not isinstance(sd, dict):
            raise ValueError(f"Step at index {i} must be a mapping")
        if "id" not in sd:
            raise ValueError(f"Step at index {i} is missing required 'id' field")
        if "action" not in sd:
            raise ValueError(f"Step '{sd['id']}' is missing required 'action' field")
        steps.append(
            StepDef(
                id=sd["id"],
                action=sd["action"],
                depends_on=sd.get("depends_on", []),
                params=sd.get("params", {}),
            )
        )

    return PipelineDef(name=name, steps=steps)


def validate(pipeline: PipelineDef) -> bool:
    """Validate a pipeline definition for correctness.

    Checks:
    - No duplicate step IDs
    - All dependency references resolve to existing step IDs
    - No circular dependencies
    """
    if not pipeline.name:
        return False

    step_ids = {s.id for s in pipeline.steps}
    if len(step_ids) != len(pipeline.steps):
        raise ValueError("Duplicate step IDs found in pipeline")

    # Validate dependency references
    for step in pipeline.steps:
        for dep in step.depends_on:
            if dep not in step_ids:
                raise ValueError(f"Step '{step.id}' depends on unknown step '{dep}'")

    # Detect cycles via DFS
    _detect_cycles(pipeline.steps, step_ids)

    return True


def _detect_cycles(steps: list[StepDef], step_ids: set[str]) -> None:
    """Raise ValueError if a cycle is found in the dependency graph."""
    adj: dict[str, set[str]] = {sid: set() for sid in step_ids}
    for s in steps:
        for dep in s.depends_on:
            adj[dep].add(s.id)

    WHITE, GRAY, BLACK = 0, 1, 2  # noqa: N806
    color: dict[str, int] = {sid: WHITE for sid in step_ids}

    def dfs(node: str) -> None:
        color[node] = GRAY
        for neighbor in adj.get(node, set()):
            if color[neighbor] == GRAY:
                raise ValueError(f"Circular dependency detected involving step '{node}'")
            if color[neighbor] == WHITE:
                dfs(neighbor)
        color[node] = BLACK

    for sid in step_ids:
        if color[sid] == WHITE:
            dfs(sid)
