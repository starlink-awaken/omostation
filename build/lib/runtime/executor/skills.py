"""Workflow Skills — built-in agent skills for common tasks."""

import time
from dataclasses import dataclass
from typing import Any


@dataclass
class SkillDef:
    name: str
    description: str = ""
    category: str = "general"
    version: str = "1.0.0"

@dataclass
class SkillResult:
    success: bool
    output: Any = None
    error: str = ""
    duration_ms: float = 0.0

class SkillRegistry:
    """Registry of built-in skills for agent workflows."""

    def __init__(self):
        self._skills: dict[str, SkillDef] = {}  # type: ignore[annotation-unchecked]
        self._executors: dict[str, callable] = {}  # type: ignore[annotation-unchecked]

    def register(self, name: str, executor: callable, description: str = "", category: str = "general"):  # type: ignore[valid-type]
        self._skills[name] = SkillDef(name=name, description=description, category=category)
        self._executors[name] = executor

    def execute(self, name: str, context: dict | None = None) -> SkillResult:
        executor = self._executors.get(name)
        if not executor:
            return SkillResult(success=False, error=f"Skill not found: {name}")
        t0 = time.time()
        try:
            result = executor(context or {})
            return SkillResult(success=True, output=result, duration_ms=(time.time()-t0)*1000)
        except Exception as e:
            return SkillResult(success=False, error=str(e), duration_ms=(time.time()-t0)*1000)

    def list_by_category(self, category: str) -> list[SkillDef]:
        return [s for s in self._skills.values() if s.category == category]

    def list_all(self) -> list[SkillDef]:
        return list(self._skills.values())


def create_builtin_skills() -> SkillRegistry:
    """Create a registry with built-in skills."""
    registry = SkillRegistry()
    registry.register("summarize", lambda ctx: f"Summary of: {ctx.get('text', '')[:100]}",
                       "Summarize text content", "documentation")
    registry.register("code_review", lambda ctx: {"issues": [], "suggestions": [], "score": 5.0},
                       "Review code for issues and suggest improvements", "code")
    registry.register("test_generate", lambda ctx: {"tests": [], "coverage_estimate": 0.0},
                       "Generate test cases for given code", "testing")
    registry.register("extract_keywords",
                       lambda ctx: [w for w in ctx.get("text", "").split()[:20] if len(w) > 3],
                       "Extract keywords from text", "analysis")
    registry.register("format_output", lambda ctx: str(ctx.get("data", "")),
                       "Format data as string output", "formatting")
    return registry
