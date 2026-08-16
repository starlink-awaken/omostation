"""Capability Registry — register and discover agent capabilities."""

from dataclasses import dataclass, field


@dataclass
class CapabilitySchema:
    name: str
    description: str = ""
    parameters: dict[str, str] = field(default_factory=dict)
    required_params: list[str] = field(default_factory=list)

    def validate(self, params: dict) -> bool:
        return all(p in params for p in self.required_params)


class CapabilityRegistry:
    """Register and discover agent capabilities."""

    def __init__(self) -> None:
        self._index: dict[str, set[str]] = {}  # type: ignore[annotation-unchecked]
        self._schemas: dict[str, CapabilitySchema] = {}  # type: ignore[annotation-unchecked]
        self._agents: dict[str, dict] = {}  # type: ignore[annotation-unchecked]

    def register_schema(self, schema: CapabilitySchema) -> None:
        self._schemas[schema.name] = schema

    def register_agent(self, agent_id: str, capabilities: list[str], metadata: dict | None = None) -> None:
        self._agents[agent_id] = metadata or {}
        for cap in capabilities:
            self._index.setdefault(cap, set()).add(agent_id)

    def deregister_agent(self, agent_id: str) -> None:
        for cap_set in self._index.values():
            cap_set.discard(agent_id)
        self._agents.pop(agent_id, None)

    def find_by_capability(self, capability: str) -> list[str]:
        return sorted(self._index.get(capability, set()))

    def find_by_capabilities(self, capabilities: list[str], match_all: bool = False) -> list[str]:
        if not capabilities:
            return []
        if match_all:
            result = self._index.get(capabilities[0], set())
            for cap in capabilities[1:]:
                result &= self._index.get(cap, set())
            return sorted(result)
        result: set[str] = set()  # type: ignore[no-redef]
        for cap in capabilities:
            result |= self._index.get(cap, set())
        return sorted(result)

    def get_agent_capabilities(self, agent_id: str) -> list[str]:
        return sorted(c for c, agents in self._index.items() if agent_id in agents)

    def list_capabilities(self) -> list[str]:
        return sorted(self._index.keys())

    def list_agents(self) -> list[str]:
        return sorted(self._agents.keys())

    def agent_count(self) -> int:
        return len(self._agents)
