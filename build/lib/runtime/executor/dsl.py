"""
DSL系统 — agentmesh迁移 (精简版)

Python DSL for agent workflows with YAML/JSON format.
支持: agent_call, skill_call, tool_call, conditional, loop, parallel, try_catch
DAG dependency resolution, async executor.

来源: agentmesh/packages/engine/src/dsl/
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

# ============================================================
# Errors
# ============================================================

class DSLError(Exception):
    """Base DSL error."""

    def __init__(self, message: str, code: str = "") -> None:
        super().__init__(message)
        self.code = code


class CircularDependencyError(DSLError):
    """Cycle detected in step dependencies."""

    def __init__(self, cycle: list[str]) -> None:
        self.cycle = cycle
        super().__init__(
            f"Circular dependency detected: {' -> '.join(cycle)}",
            code="SEM303",
        )


class StepExecutionError(DSLError):
    """A step failed during execution."""

    def __init__(self, step_name: str, message: str) -> None:
        self.step_name = step_name
        super().__init__(f"Step '{step_name}' failed: {message}", code="EXEC400")


# ============================================================
# DSL AST node types
# ============================================================

class CallType(StrEnum):
    AGENT = "agent"
    SKILL = "skill"
    TOOL = "tool"


class LoopType(StrEnum):
    FOR = "for"
    WHILE = "while"
    FOR_EACH = "for_each"


@dataclass
class DSLCall:
    """A call to an agent, skill, or tool."""
    type: CallType
    target: str


@dataclass
class DSLRetry:
    max_attempts: int = 3
    backoff_ms: int = 1000


@dataclass
class DSLStep:
    """A single step in the workflow body."""
    type: str = "step"
    name: str = ""
    call: DSLCall | None = None
    inputs: dict[str, Any] = field(default_factory=dict)
    outputs: dict[str, str] = field(default_factory=dict)
    retry: DSLRetry | None = None
    # control-flow
    test: str | None = None
    branches: list[dict[str, Any]] = field(default_factory=list)
    consequent: list[dict[str, Any]] = field(default_factory=list)
    alternate: list[dict[str, Any]] = field(default_factory=list)
    loop_type: LoopType | None = None
    variable: str | None = None
    collection: str | None = None
    body: list[dict[str, Any]] = field(default_factory=list)
    parallel_branches: list[list[dict[str, Any]]] = field(default_factory=list)
    max_concurrency: int | None = None
    try_block: list[dict[str, Any]] = field(default_factory=list)
    catch_variable: str | None = None
    catch_block: list[dict[str, Any]] = field(default_factory=list)
    finally_block: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class DSLDefinition:
    """Top-level DSL definition from YAML/JSON."""
    name: str
    description: str = ""
    version: str = "1.0"
    inputs: dict[str, Any] = field(default_factory=dict)
    outputs: dict[str, str] = field(default_factory=dict)
    steps: list[DSLStep] = field(default_factory=list)
