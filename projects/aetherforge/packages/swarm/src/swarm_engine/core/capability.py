"""Capability models and catalog — unified registry for tools and agent cards."""

from dataclasses import dataclass, field
from typing import Any

# ── Capability descriptor ────────────────────────────────────────────────


@dataclass
class Capability:
    """Universal capability descriptor for tools."""

    id: str
    name: str
    source: str  # "synapse" | "mcp" | "local" | "plugin"
    description: str = ""
    input_schema: dict | None = None
    output_schema: dict | None = None
    cost_eu: float = 1.0
    tags: list[str] = field(default_factory=list)


class CapabilityCatalog:
    """Unified registry of capabilities."""

    def __init__(self) -> None:
        self._capabilities: dict[str, Capability] = {}

    def register(self, capability: Capability) -> None:
        self._capabilities[capability.id] = capability

    def unregister(self, capability_id: str) -> bool:
        return self._capabilities.pop(capability_id, None) is not None

    def get(self, capability_id: str) -> Capability | None:
        return self._capabilities.get(capability_id)

    def discover(
        self,
        query: str = "",
        tags: list[str] | None = None,
        source: str | None = None,
    ) -> list[Capability]:
        results = list(self._capabilities.values())
        if source:
            results = [c for c in results if c.source == source]
        if tags:
            tag_set = set(tags)
            results = [c for c in results if tag_set.intersection(c.tags)]
        if query:
            q = query.lower()
            results = [c for c in results if q in c.name.lower() or q in c.description.lower()]
        return results

    def list_by_source(self, source: str) -> list[Capability]:
        return [c for c in self._capabilities.values() if c.source == source]

    def register_synapse_driver(self, driver_name: str, driver_info: dict) -> Capability:
        cap = Capability(
            id=f"synapse:{driver_name}",
            name=driver_info.get("name", driver_name),
            source="synapse",
            description=driver_info.get("description", ""),
            input_schema=driver_info.get("input_schema"),
            output_schema=driver_info.get("output_schema"),
            cost_eu=driver_info.get("cost_eu", 1.0),
            tags=driver_info.get("tags", ["llm"]),
        )
        self.register(cap)
        return cap

    def register_mcp_tool(self, tool_name: str, tool_info: dict) -> Capability:
        cap = Capability(
            id=f"mcp:{tool_name}",
            name=tool_info.get("name", tool_name),
            source="mcp",
            description=tool_info.get("description", ""),
            input_schema=tool_info.get("inputSchema"),
            output_schema=tool_info.get("outputSchema"),
            cost_eu=tool_info.get("cost_eu", 0.5),
            tags=tool_info.get("tags", ["tool"]),
        )
        self.register(cap)
        return cap

    def to_agent_card(self) -> dict:
        return {
            "capabilities": [
                {
                    "id": c.id,
                    "name": c.name,
                    "source": c.source,
                    "description": c.description,
                    "cost_eu": c.cost_eu,
                    "tags": c.tags,
                }
                for c in self._capabilities.values()
            ],
            "total": len(self._capabilities),
        }

    def __len__(self) -> int:
        return len(self._capabilities)


# ── Agent / Task request models ──────────────────────────────────────────


@dataclass
class AgentCard:
    agent_id: str
    agent_instance_id: str
    persona: str
    capabilities: list[str]
    max_concurrency: int = 1
    priority_affinity: list[int] = field(default_factory=lambda: [0, 1, 2, 3])
    endpoint: str = "local"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TaskRequest:
    task_id: str
    required_capabilities: list[str]
    preferred_capabilities: list[str] = field(default_factory=list)
    priority: int = 2
    payload: dict[str, Any] = field(default_factory=dict)
    timeout: float = 3600.0
