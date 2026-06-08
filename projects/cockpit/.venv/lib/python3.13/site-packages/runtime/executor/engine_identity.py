"""Engine Identity Manager — declare, validate, register, query identities.

Ported from agentmesh identity-manager.ts.

"""

from __future__ import annotations

import re

from runtime.executor.engine_types import (
    AgentCapability,
    AgentDefinition,
    AgentIdentity,
    IdentityValidationResult,
    SovereigntyLevel,
)


class IdentityManager:
    """Manages agent identity declaration, validation, and registration."""

    def __init__(self) -> None:
        self._identities: dict[str, AgentIdentity] = {}
        self._reverse_dns_re = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*(\.[a-zA-Z_][a-zA-Z0-9_\-]*)+$")

    def declare(self, agent: AgentDefinition) -> AgentIdentity:
        """Extract AgentIdentity from an AgentDefinition."""
        name = agent.name
        agent_id = f"agent://{name.lower().replace(' ', '-')}" if name else self._generate_id(name)
        identity = AgentIdentity(
            id=agent_id,
            name=name or agent_id,
            role=agent.description or "generic agent",
            sovereignty_level=SovereigntyLevel.CONDITIONAL,
            capabilities=[AgentCapability(id=c, description=c) for c in (agent.capabilities or [])],
        )
        if agent.identity is not None:
            if agent.identity.personality:
                identity.personality = agent.identity.personality
            if agent.identity.communication_style:
                identity.communication_style = agent.identity.communication_style
            if agent.identity.boundaries:
                identity.boundaries = agent.identity.boundaries[:]
        return identity

    def validate(self, identity: AgentIdentity) -> IdentityValidationResult:
        """Validate identity field completeness and format."""
        errors: list[str] = []
        warnings: list[str] = []

        if not identity.id:
            errors.append("A1.2: identity.id is required")
        elif not self._reverse_dns_re.match(identity.id):
            errors.append(f'A1.2: identity.id "{identity.id}" is not valid reverse-DNS format')

        if not identity.name:
            errors.append("A1.3: identity.name is required")
        if not identity.role:
            errors.append("A1.4: identity.role is required")

        valid_levels = {s.value for s in SovereigntyLevel}
        if identity.sovereignty_level.value not in valid_levels:
            errors.append(f"A1.5: sovereigntyLevel must be one of: {', '.join(sorted(valid_levels))}")

        if not identity.capabilities:
            errors.append("A1.6: capabilities list cannot be empty")
        else:
            for i, cap in enumerate(identity.capabilities):
                if not cap.id:
                    errors.append(f"A1.6: capabilities[{i}] missing id")
                if not cap.description:
                    warnings.append(f'A1.6: capabilities[{i}] ("{cap.id or ""}") missing description')

        return IdentityValidationResult(valid=len(errors) == 0, errors=errors, warnings=warnings)

    def register_agent(self, agent_id: str, identity: AgentIdentity) -> None:
        self._identities[agent_id] = identity

    def get_identity(self, agent_id: str) -> AgentIdentity | None:
        return self._identities.get(agent_id)

    def get_all_identities(self) -> list[AgentIdentity]:
        return list(self._identities.values())

    def has_identity(self, agent_id: str) -> bool:
        return agent_id in self._identities

    def remove_identity(self, agent_id: str) -> bool:
        return self._identities.pop(agent_id, None) is not None

    @staticmethod
    def _generate_id(name: str) -> str:
        return f"urn:hermes:agent:{name.lower().replace(' ', '-')}"
