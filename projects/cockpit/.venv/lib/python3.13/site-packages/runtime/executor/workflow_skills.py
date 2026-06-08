"""Workflow Skills — skill registry, executor, and builtin skill definitions."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------


@dataclass
class SkillVersion:
    major: int = 1
    minor: int = 0
    patch: int = 0


@dataclass
class SkillMetadata:
    skill_id: str
    name: str
    type: str = "custom"  # analysis | generation | transformation | validation | integration | orchestration | custom
    version: SkillVersion = field(default_factory=SkillVersion)
    description: str = ""
    publisher: str = ""
    tags: list[str] = field(default_factory=list)


@dataclass
class SkillInputSchema:
    name: str
    type: str = "string"
    description: str = ""
    required: bool = True


@dataclass
class SkillConfig:
    metadata: SkillMetadata
    agent_template: str = ""
    execution_mode: str = "sync"
    inputs: list[SkillInputSchema] = field(default_factory=list)
    tools: list[str] = field(default_factory=list)
    token_budget: int = 5000
    timeout_ms: int = 30_000


@dataclass
class SkillExecutionRequest:
    skill_id: str
    inputs: dict[str, Any] = field(default_factory=dict)
    options: dict[str, Any] = field(default_factory=dict)


@dataclass
class SkillExecutionResult:
    execution_id: str
    skill_id: str
    status: str = "running"  # running | completed | failed | cancelled
    output: Any = None
    error: str | None = None
    token_usage: int = 0
    started_at: float = 0.0
    completed_at: float | None = None


# ---------------------------------------------------------------------------
# Builtin Skills
# ---------------------------------------------------------------------------

BUILTIN_SKILLS: list[SkillConfig] = [
    SkillConfig(
        metadata=SkillMetadata(
            skill_id="honeycomb.code.review",
            name="Code Review",
            type="validation",
            version=SkillVersion(1, 0, 0),
            description="Reviews code for quality issues and vulnerabilities",
            publisher="honeycomb",
            tags=["code", "review", "quality"],
        ),
        inputs=[
            SkillInputSchema(name="code", description="Source code to review"),
            SkillInputSchema(name="language", description="Programming language", required=False),
        ],
        agent_template="Review the following {{language}} code:\n```{{language}}\n{{code}}\n```",
    ),
    SkillConfig(
        metadata=SkillMetadata(
            skill_id="honeycomb.code.test",
            name="Test Generator",
            type="generation",
            version=SkillVersion(1, 0, 0),
            description="Generates unit tests from source code",
            publisher="honeycomb",
            tags=["code", "testing"],
        ),
        inputs=[
            SkillInputSchema(name="code", description="Source code"),
            SkillInputSchema(name="language", description="Programming language", required=False),
        ],
        token_budget=8000,
        agent_template="Generate unit tests for:\n```{{language}}\n{{code}}\n```",
    ),
    SkillConfig(
        metadata=SkillMetadata(
            skill_id="honeycomb.doc.generate",
            name="Document Generator",
            type="generation",
            version=SkillVersion(1, 0, 0),
            description="Generates documentation from content",
            publisher="honeycomb",
            tags=["documentation"],
        ),
        inputs=[
            SkillInputSchema(name="content", description="Content to document"),
            SkillInputSchema(name="format", description="Output format", required=False),
        ],
        agent_template="Generate documentation in {{format}} format for:\n{{content}}",
    ),
    SkillConfig(
        metadata=SkillMetadata(
            skill_id="honeycomb.code.refactor",
            name="Code Refactor",
            type="transformation",
            version=SkillVersion(1, 0, 0),
            description="Refactors code per specified rules",
            publisher="honeycomb",
            tags=["code", "refactor"],
        ),
        inputs=[
            SkillInputSchema(name="code", description="Source code"),
            SkillInputSchema(name="language", description="Language", required=False),
        ],
        token_budget=6000,
        agent_template="Refactor the following {{language}} code:\n```{{language}}\n{{code}}\n```",
    ),
]


# ---------------------------------------------------------------------------
# SkillRegistry
# ---------------------------------------------------------------------------


class SkillRegistry:
    """Manages skill registration, querying, and versioning."""

    def __init__(self) -> None:
        self._skills: dict[str, dict[str, SkillConfig]] = {}  # skill_id -> version_str -> config
        for s in BUILTIN_SKILLS:
            self.register(s)

    def register(self, config: SkillConfig) -> str:
        sid = config.metadata.skill_id
        vstr = self._version_str(config.metadata.version)

        self._skills.setdefault(sid, {})
        if vstr in self._skills[sid]:
            msg = f"Skill {sid} version {vstr} already registered"
            raise ValueError(msg)

        self._skills[sid][vstr] = config
        return sid

    def unregister(self, skill_id: str, version: str | None = None) -> None:
        if skill_id not in self._skills:
            return
        if version:
            self._skills[skill_id].pop(version, None)
            if not self._skills[skill_id]:
                del self._skills[skill_id]
        else:
            del self._skills[skill_id]

    def get(self, skill_id: str) -> SkillConfig | None:
        versions = self._skills.get(skill_id)
        if not versions:
            return None
        return self._latest(versions)

    def has(self, skill_id: str) -> bool:
        return skill_id in self._skills

    def list(self) -> list[SkillConfig]:
        return [self._latest(v) for v in self._skills.values() if self._latest(v) is not None]  # type: ignore[misc]

    def search(self, query: str) -> list[SkillConfig]:  # type: ignore[valid-type]
        q = query.lower()
        results: list[SkillConfig] = []
        for versions in self._skills.values():
            cfg = self._latest(versions)
            if cfg is None:
                continue
            text = f"{cfg.metadata.skill_id} {cfg.metadata.name} {cfg.metadata.description}".lower()
            if q in text:
                results.append(cfg)
        return results

    @staticmethod
    def _latest(versions: dict[str, SkillConfig]) -> SkillConfig | None:
        if not versions:
            return None
        return max(versions.values(), key=lambda c: (c.metadata.version.major, c.metadata.version.minor, c.metadata.version.patch))

    @staticmethod
    def _version_str(v: SkillVersion) -> str:
        return f"{v.major}.{v.minor}.{v.patch}"


# ---------------------------------------------------------------------------
# SkillExecutor
# ---------------------------------------------------------------------------


class SkillExecutor:
    """Executes skills — validates inputs, builds prompts, simulates output."""

    def __init__(self, registry: SkillRegistry) -> None:
        self._registry = registry
        self._executions: dict[str, SkillExecutionResult] = {}

    async def execute(self, request: SkillExecutionRequest) -> SkillExecutionResult:
        config = self._registry.get(request.skill_id)
        exec_id = f"exec-{uuid.uuid4().hex[:12]}"
        started = time.time()

        if config is None:
            return SkillExecutionResult(
                execution_id=exec_id,
                skill_id=request.skill_id,
                status="failed",
                error=f"Skill {request.skill_id} not found",
                started_at=started,
                completed_at=time.time(),
            )

        validation = self._validate_inputs(config, request.inputs)
        if not validation[0]:
            return SkillExecutionResult(
                execution_id=exec_id,
                skill_id=request.skill_id,
                status="failed",
                error=validation[1],
                started_at=started,
                completed_at=time.time(),
            )

        prompt = self._build_prompt(config, request.inputs)
        tokens = len(prompt) // 4
        output = self._simulate_output(config.metadata.skill_id, request.inputs)

        result = SkillExecutionResult(
            execution_id=exec_id,
            skill_id=request.skill_id,
            status="completed",
            output=output,
            token_usage=tokens,
            started_at=started,
            completed_at=time.time(),
        )
        self._executions[exec_id] = result
        return result

    async def execute_batch(self, requests: list[SkillExecutionRequest]) -> list[SkillExecutionResult]:
        results: list[SkillExecutionResult] = []
        for req in requests:
            results.append(await self.execute(req))
        return results

    def cancel(self, execution_id: str) -> None:
        result = self._executions.get(execution_id)
        if result and result.status == "running":
            result.status = "cancelled"
            result.completed_at = time.time()

    def get_status(self, execution_id: str) -> SkillExecutionResult | None:
        return self._executions.get(execution_id)

    # -- Internal ------------------------------------------------------------

    def _validate_inputs(self, config: SkillConfig, inputs: dict[str, Any]) -> tuple[bool, str]:
        for inp in config.inputs:
            if inp.required and inp.name not in inputs:
                return False, f"Required input '{inp.name}' missing"
        return True, ""

    def _build_prompt(self, config: SkillConfig, inputs: dict[str, Any]) -> str:
        prompt = config.agent_template
        for k, v in inputs.items():
            prompt = prompt.replace("{{" + k + "}}", str(v))
        return prompt

    def _simulate_output(self, skill_id: str, inputs: dict[str, Any]) -> Any:
        if skill_id == "honeycomb.code.review":
            return {"issues": [], "summary": "Code looks clean", "score": 90}
        if skill_id == "honeycomb.code.test":
            return "def test_example():\n    assert True"
        if skill_id == "honeycomb.doc.generate":
            return f"# Documentation\n\n{inputs.get('content', '')}"
        if skill_id == "honeycomb.code.refactor":
            return inputs.get("code", "# Refactored code")
        if skill_id == "honeycomb.git.commit":
            return {"hash": uuid.uuid4().hex, "message": inputs.get("message", "")}
        return {"executed": True, "inputs": inputs}
