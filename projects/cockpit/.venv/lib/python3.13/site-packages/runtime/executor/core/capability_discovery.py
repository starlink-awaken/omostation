"""Agent capability discovery and indexing.

Port of agentmesh engine capability-schema.ts and capability-discovery.ts.
"""

from __future__ import annotations

import enum
import time
from dataclasses import dataclass, field
from typing import Any


class CapabilityType(enum.StrEnum):
    ANALYSIS = "analysis"
    GENERATION = "generation"
    VALIDATION = "validation"
    TRANSFORMATION = "transformation"
    EXECUTION = "execution"
    COORDINATION = "coordination"
    MONITORING = "monitoring"
    CUSTOM = "custom"


class CapabilityLevel(enum.StrEnum):
    BASIC = "basic"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"


CAPABILITY_LEVEL_VALUES: dict[CapabilityLevel, int] = {
    CapabilityLevel.BASIC: 0, CapabilityLevel.INTERMEDIATE: 1,
    CapabilityLevel.ADVANCED: 2, CapabilityLevel.EXPERT: 3,
}


def meets_capability_level(actual: CapabilityLevel, required: CapabilityLevel) -> bool:
    return CAPABILITY_LEVEL_VALUES[actual] >= CAPABILITY_LEVEL_VALUES[required]


@dataclass
class IOSchema:
    type: str
    description: str | None = None
    properties: dict[str, IOSchema] | None = None
    items: IOSchema | None = None
    required: list[str] | None = None
    enum: list[Any] | None = None
    format: str | None = None
    pattern: str | None = None
    minimum: float | None = None
    maximum: float | None = None
    min_length: int | None = None
    max_length: int | None = None


@dataclass
class CapabilityDependency:
    capability: str
    required: bool = True
    min_level: CapabilityLevel | None = None


@dataclass
class PerformanceMetrics:
    avg_duration_ms: float | None = None
    avg_tokens: float | None = None
    success_rate: float | None = None


@dataclass
class CapabilityDefinition:
    id: str
    type: CapabilityType
    name: str
    description: str
    level: CapabilityLevel = CapabilityLevel.INTERMEDIATE
    input: IOSchema | None = None
    output: IOSchema | None = None
    dependencies: list[CapabilityDependency] | None = None
    tags: list[str] | None = None
    version: str | None = None
    performance: PerformanceMetrics | None = None


@dataclass
class AgentCapabilities:
    agent_name: str
    capabilities: list[CapabilityDefinition] = field(default_factory=list)
    agent_version: str = "1.0.0"
    default_level: CapabilityLevel = CapabilityLevel.INTERMEDIATE


@dataclass
class DiscoveredCapability:
    capability: CapabilityDefinition
    agent_name: str
    agent_layer: str
    agent_type: str
    discovered_at: float = 0.0


@dataclass
class DiscoveryConfig:
    enable_cache: bool = True
    cache_ttl: int = 60000
    validate: bool = True


@dataclass
class CapabilityMatchRequest:
    type: str | None = None
    tags: list[str] | None = None
    input: Any | None = None
    output_schema: IOSchema | None = None
    min_level: CapabilityLevel | None = None
    max_duration_ms: float | None = None
    max_tokens: float | None = None
    mode: str = "fuzzy"


@dataclass
class CapabilityMatchResult:
    agent_name: str
    capability: CapabilityDefinition
    score: float
    reasons: list[str] = field(default_factory=list)


@dataclass
class CapabilityValidationResult:
    valid: bool = False
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


_KWT = CapabilityType
_INFERRED = dict(zip(
    ["analysis", "analyze", "check", "generate", "create", "write",
     "validate", "verify", "review", "transform", "convert", "translate",
     "execute", "run", "call", "monitor", "track", "observe"],
    [_KWT.ANALYSIS] * 3 + [_KWT.GENERATION] * 3 + [_KWT.VALIDATION] * 3 +
    [_KWT.TRANSFORMATION] * 3 + [_KWT.EXECUTION] * 3 + [_KWT.MONITORING] * 3,
))
_LTAGS = {"L1": "research", "L2": "decision", "L3": "execution", "L4": "feedback", "governance": "governance"}
_LTYPES = {"L1": _KWT.ANALYSIS, "L2": _KWT.COORDINATION, "L3": _KWT.EXECUTION, "L4": _KWT.VALIDATION, "governance": _KWT.MONITORING}


def infer_capability_type(name: str, layer: str = "custom") -> CapabilityType:
    for keyword, ctype in _INFERRED.items():
        if keyword in name.lower():
            return ctype
    return _LTYPES.get(layer, CapabilityType.CUSTOM)


def infer_tag_from_layer(layer: str) -> str:
    return _LTAGS.get(layer, "general")


class CapabilityDiscovery:
    """Agent capability discovery with multi-dimensional indexing."""

    def __init__(self, config: DiscoveryConfig | None = None) -> None:
        self.config = config or DiscoveryConfig()
        self._by_id: dict[str, DiscoveredCapability] = {}
        self._by_type: dict[str, list[DiscoveredCapability]] = {}
        self._by_level: dict[str, list[DiscoveredCapability]] = {}
        self._by_agent: dict[str, list[DiscoveredCapability]] = {}
        self._by_tag: dict[str, list[DiscoveredCapability]] = {}
        self._agent_caps: dict[str, AgentCapabilities] = {}
        self._cache_ts: float = 0.0

    def _clear(self) -> None:
        for k in ("_by_id", "_by_type", "_by_level", "_by_agent", "_by_tag", "_agent_caps"):
            getattr(self, k).clear()
        self._cache_ts = 0.0

    def discover_from_agents(self, agents: list[dict[str, Any]]) -> None:
        self._clear()
        for a in agents:
            self.discover_from_agent(a)
        self._cache_ts = time.time()

    def discover_from_agent(self, agent: dict[str, Any]) -> None:
        name, layer = agent.get("name", "unknown"), agent.get("layer", "custom")
        atype = agent.get("type", "custom")
        defs, seen, tag = [], set(), infer_tag_from_layer(layer)
        for cid in agent.get("capabilities") or []:
            if (full := f"{name}-{cid}") not in seen:
                seen.add(full)
                defs.append(CapabilityDefinition(id=full, type=infer_capability_type(cid, layer), name=cid, description=f"Capability to {cid} ({name})", level=CapabilityLevel.INTERMEDIATE, tags=[tag]))
        for tool in agent.get("tools") or []:
            if (full := f"{name}-{tool}") not in seen:
                seen.add(full)
                defs.append(CapabilityDefinition(id=full, type=infer_capability_type(tool, layer), name=tool, description=f"Tool: {tool} ({name})", level=CapabilityLevel.BASIC, tags=["tool", tag]))
        self._agent_caps[name] = AgentCapabilities(agent_name=name, capabilities=defs)
        for cap in defs:
            dc = DiscoveredCapability(capability=cap, agent_name=name, agent_layer=layer, agent_type=atype, discovered_at=time.time())
            self._by_id[cap.id] = dc
            self._by_type.setdefault(cap.type.value, []).append(dc)
            self._by_level.setdefault(cap.level.value, []).append(dc)
            self._by_agent.setdefault(name, []).append(dc)
            for t in cap.tags or []:
                self._by_tag.setdefault(t, []).append(dc)

    def find_all(self) -> list[DiscoveredCapability]:
        return list(self._by_id.values())
    def find_by_id(self, cap_id: str) -> DiscoveredCapability | None:
        return self._by_id.get(cap_id)
    def find_by_type(self, ctype: CapabilityType) -> list[DiscoveredCapability]:
        return list(self._by_type.get(ctype.value, []))
    def find_by_level(self, level: CapabilityLevel) -> list[DiscoveredCapability]:
        return list(self._by_level.get(level.value, []))
    def find_by_agent(self, agent_name: str) -> list[DiscoveredCapability]:
        return list(self._by_agent.get(agent_name, []))
    def find_by_tag(self, tag: str) -> list[DiscoveredCapability]:
        return list(self._by_tag.get(tag, []))

    def find_by_tags(self, tags: list[str], match_all: bool = False) -> list[DiscoveredCapability]:
        if match_all:
            return [dc for dc in self._by_id.values() if all(t in (dc.capability.tags or []) for t in tags)]
        seen: dict[str, DiscoveredCapability] = {}
        for tag in tags:
            for dc in self._by_tag.get(tag, []):
                seen[dc.capability.id] = dc
        return list(seen.values())

    def get_discovered_agents(self) -> list[str]:
        return list(self._by_agent.keys())

    def get_agent_capabilities(self, agent_name: str) -> AgentCapabilities | None:
        return self._agent_caps.get(agent_name)

    def get_statistics(self) -> dict[str, Any]:
        caps = self.find_all()
        by_type: dict[str, int] = {}
        by_level: dict[str, int] = {}
        by_agent: dict[str, int] = {}
        tag_counts: dict[str, int] = {}
        for dc in caps:
            by_type[dc.capability.type.value] = by_type.get(dc.capability.type.value, 0) + 1
            by_level[dc.capability.level.value] = by_level.get(dc.capability.level.value, 0) + 1
            by_agent[dc.agent_name] = by_agent.get(dc.agent_name, 0) + 1
            for t in dc.capability.tags or []:
                tag_counts[t] = tag_counts.get(t, 0) + 1
        top = sorted([{"tag": t, "count": c} for t, c in tag_counts.items()], key=lambda x: -x["count"])[:10]  # type: ignore[operator]
        return {"total_capabilities": len(caps), "capabilities_by_type": by_type, "capabilities_by_level": by_level, "capabilities_by_agent": by_agent, "total_tags": len(tag_counts), "top_tags": top}

    def clear_cache(self) -> None:
        self._clear()

    def get_cache_status(self) -> dict[str, Any]:
        age = time.time() - self._cache_ts if self._cache_ts > 0 else 0
        return {"enabled": self.config.enable_cache, "timestamp": self._cache_ts, "age": age, "capability_count": len(self._by_id), "agent_count": len(self._by_agent)}
