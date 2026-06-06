"""Configuration loader — load engine and project config from JSON files.

Migrated from agentmesh config-loader.ts.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class RiskThresholds:
    file_count: dict = field(default_factory=lambda: {"low": 3, "medium": 10, "high": 20})
    security_keywords_enabled: bool = True
    custom_rules: list[dict] = field(default_factory=list)


@dataclass
class EngineConfig:
    db_path: str = "./honeycomb.db"
    agents_root: str = "../agents"
    domains_root: str = "../domains"
    output_dir: str = "./docs/honeycomb"
    log_level: str = "info"
    log_file: str | None = None
    default_token_budget: int = 100_000
    max_concurrent_agents: int = 5
    auto_checkpoint: bool = True
    risk_thresholds: RiskThresholds = field(default_factory=RiskThresholds)


@dataclass
class ProjectConfig:
    name: str
    description: str
    archetype: str
    goals: list[str]
    constraints: list[str] | None = None
    domain: str | None = None
    token_budget: int | None = None


class ConfigLoader:
    """Load and merge engine/project configuration from JSON files."""

    def __init__(self) -> None:
        self._default = self._make_default_config()

    def load_engine_config(self, config_path: str | None = None) -> EngineConfig:
        if not config_path or not Path(config_path).exists():
            return self._make_default_config()
        try:
            raw = Path(config_path).read_text(encoding="utf-8")
            parsed = json.loads(raw)
            return self._merge(parsed)
        except (json.JSONDecodeError, OSError):
            return self._make_default_config()

    def load_project_config(self, config_path: str) -> ProjectConfig:
        resolved = Path(config_path).resolve()
        if not resolved.exists():
            raise FileNotFoundError(f"Project config not found: {resolved}")
        raw = resolved.read_text(encoding="utf-8")
        parsed = json.loads(raw)
        name = parsed.get("name")
        desc = parsed.get("description")
        archetype = parsed.get("archetype")
        goals = parsed.get("goals")
        if not name or not isinstance(name, str):
            raise ValueError("Project config missing required field: name")
        if not desc or not isinstance(desc, str):
            raise ValueError("Project config missing required field: description")
        if not archetype or not isinstance(archetype, str):
            raise ValueError("Project config missing required field: archetype")
        if not isinstance(goals, list):
            raise ValueError("Project config missing required field: goals")
        return ProjectConfig(
            name=name,
            description=desc,
            archetype=archetype,
            goals=goals,
            constraints=parsed.get("constraints"),
            domain=parsed.get("domain"),
            token_budget=parsed.get("token_budget"),
        )

    def assess_complexity(self, config: ProjectConfig) -> str:
        """Assess project complexity based on goals count and modifiers."""
        goals_count = len(config.goals)
        constraints_count = len(config.constraints) if config.constraints else 0
        if goals_count <= 3:
            level = "simple"
        elif goals_count <= 7:
            level = "standard"
        elif goals_count <= 15:
            level = "advanced"
        else:
            level = "enterprise"
        if constraints_count > 5 or config.archetype == "custom":
            level = self._bump(level)
        return level

    def get_default_config(self) -> EngineConfig:
        return self._make_default_config()

    def _make_default_config(self) -> EngineConfig:
        return EngineConfig(risk_thresholds=RiskThresholds())

    def _merge(self, partial: dict) -> EngineConfig:
        defaults = self._make_default_config()
        rt = partial.get("risk_thresholds", {})
        merged_rt = RiskThresholds(
            file_count={**defaults.risk_thresholds.file_count, **rt.get("file_count", {})},
            security_keywords_enabled=rt.get("security_keywords_enabled", defaults.risk_thresholds.security_keywords_enabled),
            custom_rules=rt.get("custom_rules", list(defaults.risk_thresholds.custom_rules)),
        )
        return EngineConfig(
            db_path=partial.get("db_path", defaults.db_path),
            agents_root=partial.get("agents_root", defaults.agents_root),
            domains_root=partial.get("domains_root", defaults.domains_root),
            output_dir=partial.get("output_dir", defaults.output_dir),
            log_level=partial.get("log_level", defaults.log_level),
            log_file=partial.get("log_file"),
            default_token_budget=partial.get("default_token_budget", defaults.default_token_budget),
            max_concurrent_agents=partial.get("max_concurrent_agents", defaults.max_concurrent_agents),
            auto_checkpoint=partial.get("auto_checkpoint", defaults.auto_checkpoint),
            risk_thresholds=merged_rt,
        )

    @staticmethod
    def _bump(level: str) -> str:
        mapping = {"simple": "standard", "standard": "advanced", "advanced": "enterprise", "enterprise": "enterprise"}
        return mapping.get(level, "standard")
