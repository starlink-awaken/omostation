"""Agent Card — A2A-compatible agent metadata model.

Follows the Agent2Agent (A2A) Agent Card specification:
  https://agent2agent.info/docs/concepts/agentcard/

Each registered service in Agora can expose an Agent Card describing its
identity, capabilities, skills, and interaction modes. Cards are auto-generated
from ServiceConfig + enriched with runtime tool metadata from the proxy registry.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentSkill:
    """A single capability unit the agent can perform."""

    id: str
    name: str
    description: str = ""
    tags: list[str] = field(default_factory=list)
    examples: list[str] = field(default_factory=list)
    inputModes: list[str] | None = None  # noqa: N815
    outputModes: list[str] | None = None  # noqa: N815

    def to_dict(self) -> dict:
        d: dict[str, Any] = {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "tags": self.tags,
        }
        if self.examples:
            d["examples"] = self.examples
        if self.inputModes:
            d["inputModes"] = self.inputModes
        if self.outputModes:
            d["outputModes"] = self.outputModes
        return d


@dataclass
class AgentCard:
    """A2A-compatible agent metadata — the agent's 'business card'.

    Hosted at /.well-known/agent-card.json for agent-to-agent discovery.
    """

    # Required fields
    name: str
    description: str
    url: str
    version: str

    # Optional metadata
    provider: dict | None = None  # {"organization": str, "url": str}
    documentationUrl: str | None = None  # noqa: N815

    # Capabilities
    capabilities: dict = field(
        default_factory=lambda: {
            "streaming": True,
            "pushNotifications": False,
            "stateTransitionHistory": False,
        }
    )

    # Authentication (intended to match OpenAPI auth structure)
    authentication: dict = field(
        default_factory=lambda: {
            "schemes": [],
        }
    )

    # Default interaction modes across all skills
    defaultInputModes: list[str] = field(default_factory=lambda: ["text"])  # noqa: N815
    defaultOutputModes: list[str] = field(default_factory=lambda: ["text"])  # noqa: N815

    # Specific capability units
    skills: list[AgentSkill] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Serialize to A2A-compatible JSON dict."""
        d: dict[str, Any] = {
            "name": self.name,
            "description": self.description,
            "url": self.url,
            "version": self.version,
            "capabilities": self.capabilities,
            "authentication": self.authentication,
            "defaultInputModes": self.defaultInputModes,
            "defaultOutputModes": self.defaultOutputModes,
            "skills": [s.to_dict() for s in self.skills],
        }
        if self.provider:
            d["provider"] = self.provider
        if self.documentationUrl:
            d["documentationUrl"] = self.documentationUrl
        return d


def service_to_agent_card(
    name: str,
    description: str,
    protocol: str = "mcp",
    mcp_endpoint: str = "",
    port: int = 0,
    tags: list[str] | None = None,
    tools: list[dict] | None = None,
    has_auth: bool = False,
    has_push_notifications: bool = False,
    has_state_transitions: bool = False,
    provider_info: dict | None = None,
    documentation_url: str = "",
) -> AgentCard:
    """Convert a registered service into an Agent Card.

    Args:
        name: Service name (e.g., 'minerva')
        description: Human-readable description
        protocol: Communication protocol (mcp/rest/grpc/stdio)
        mcp_endpoint: Endpoint URL or stdio:// identifier
        port: Service port number
        tags: Service tags
        tools: List of MCP tool schemas from list_tools() response.
               Each item has 'name', 'description', 'inputSchema' etc.
        has_auth: Whether API Key authentication is configured
        has_push_notifications: Whether push notification callbacks are registered
        has_state_transitions: Whether state transition history is available
        provider_info: Provider metadata dict (organization, url)
        documentation_url: Link to service documentation

    Returns:
        An AgentCard instance ready for serialization.
    """
    # Build service URL
    if mcp_endpoint and mcp_endpoint.startswith("http"):
        base_url = mcp_endpoint.rstrip("/mcp").rstrip("/")
    elif port:
        base_url = f"http://localhost:{port}"
    else:
        base_url = f"agora://{name}"

    # Build skills from tools
    skills: list[AgentSkill] = []
    if tools:
        for tool in tools or []:
            tool_name = tool.get("name", "")
            tool_desc = tool.get("description", "")
            tool.get("inputSchema", tool.get("parameters", {}))

            skill = AgentSkill(
                id=f"{name}.{tool_name}",
                name=tool_name,
                description=tool_desc or "",
                tags=tags or [],
            )
            skills.append(skill)

    # If no tools from proxy, create a generic skill from description
    if not skills:
        skills.append(
            AgentSkill(
                id=name,
                name=name,
                description=description or f"Agora service: {name}",
                tags=tags or [],
            )
        )

    # Build authentication schemes
    auth_schemes: list[dict] = []
    if has_auth:
        auth_schemes.append(
            {
                "scheme": "api_key",
                "in": "header",
                "name": "X-API-Key",
            }
        )

    return AgentCard(
        name=name,
        description=description or f"Agora service: {name}",
        url=base_url,
        version="1.0.0",
        capabilities={
            "streaming": protocol in ("mcp", "websocket"),
            "pushNotifications": has_push_notifications,
            "stateTransitionHistory": has_state_transitions,
        },
        authentication={
            "schemes": auth_schemes,
        },
        provider=provider_info,
        documentationUrl=documentation_url or None,
        defaultInputModes=["text"],
        defaultOutputModes=["text"],
        skills=skills,
    )
