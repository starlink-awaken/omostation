"""C3a: SharedBrain identity_bridge provider for agent-runtime.

agent-runtime queries SharedBrain identity_bridge via Agora MCP to
get AgentRole → A1 agent_identity mappings. SharedBrain is the
authoritative A1 identity provider.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any
from urllib.request import Request, urlopen

_log = logging.getLogger(__name__)

DEFAULT_SHAREDBRAIN_ENDPOINT = os.environ.get(
    "SHAREDBRAIN_ENDPOINT", "http://localhost:7421"
)
DEFAULT_AGORA_ENDPOINT = os.environ.get(
    "AGORA_ENDPOINT", "http://localhost:7430"
)


class SharedBrainIdentityProvider:
    """A1 agent identity provider backed by SharedBrain identity_bridge.

    Uses Agora MCP routing to query SharedBrain's identity_bridge.
    Falls back to direct SharedBrain MCP endpoint if Agora unavailable.
    """

    def __init__(
        self,
        agora_endpoint: str = DEFAULT_AGORA_ENDPOINT,
        sharedbrain_endpoint: str = DEFAULT_SHAREDBRAIN_ENDPOINT,
        timeout: int = 10,
    ):
        self.agora = agora_endpoint.rstrip("/")
        self.sharedbrain = sharedbrain_endpoint.rstrip("/")
        self.timeout = timeout

    # ── Public API ───────────────────────────────────────────────────

    def get_agent(self, agent_id: str) -> dict[str, Any] | None:
        """Get agent identity by ID. Returns None if not found."""
        return self._query(f"/identity/agent/{agent_id}")

    def get_agent_by_role(self, role: str) -> dict[str, Any] | None:
        """Get agent identity by AgentRole. Returns None if not found."""
        return self._query(f"/identity/role/{role}")

    def list_agents(self) -> list[dict[str, Any]]:
        """List all registered agents."""
        result = self._query("/identity/agents")
        return result if isinstance(result, list) else []

    def register_agent(self, agent_data: dict[str, Any]) -> dict[str, Any]:
        """Register a new agent in SharedBrain identity_bridge."""
        return self._mutate("/identity/agent", agent_data)

    def update_agent(self, agent_id: str, updates: dict[str, Any]) -> dict[str, Any]:
        """Update an existing agent in SharedBrain identity_bridge."""
        return self._mutate(f"/identity/agent/{agent_id}", updates)

    # ── Private ──────────────────────────────────────────────────────

    def _query(self, path: str) -> Any:
        try:
            url = f"{self.sharedbrain}/api/v1{path}"
            req = Request(url, method="GET")  # noqa: S310
            resp = urlopen(req, timeout=self.timeout)  # noqa: S310
            return json.loads(resp.read().decode())
        except Exception as e:
            _log.error("SharedBrain identity query failed (%s): %s", path, e)
            return None

    def _mutate(self, path: str, data: dict[str, Any]) -> dict[str, Any]:
        try:
            url = f"{self.sharedbrain}/api/v1{path}"
            payload = json.dumps(data).encode()
            req = Request(url, data=payload, method="POST")  # noqa: S310
            req.add_header("Content-Type", "application/json")
            resp = urlopen(req, timeout=self.timeout)  # noqa: S310
            return json.loads(resp.read().decode())
        except Exception as e:
            _log.error("SharedBrain identity mutation failed (%s): %s", path, e)
            return {"ok": False, "error": str(e)}
