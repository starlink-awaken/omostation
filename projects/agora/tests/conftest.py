"""Pytest fixtures for agora tests."""

from __future__ import annotations

import os
import socket
from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def test_data_dir() -> Path:
    """Return the test data directory."""
    return Path(__file__).parent / "data"


@pytest.fixture(scope="session")
def network_available() -> bool:
    """Check if network access (github.com) is available.

    Returns True if github.com:443 is reachable within 2 seconds.
    Used by tests marked with @pytest.mark.network.
    """
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        result = sock.connect_ex(("github.com", 443))
        sock.close()
        return result == 0
    except Exception:
        return False


@pytest.fixture(autouse=True)
def _skip_if_no_network(request: pytest.FixtureRequest, network_available: bool):
    """Skip network tests when network is unavailable."""
    if request.node.get_closest_marker("network") and not network_available:
        pytest.skip("requires network access to github.com")


@pytest.fixture(scope="session", autouse=True)
def clean_env():
    """Clean up env variables that might interfere with tests."""
    env_keys = [k for k in os.environ if k.startswith(("AGORA_", "OPENAI_", "ANTHROPIC_"))]
    saved = {k: os.environ[k] for k in env_keys}
    for k in env_keys:
        del os.environ[k]
    yield
    os.environ.update(saved)


class FakeToolCatalog:
    """In-memory fake of ToolCatalog for testing.

    Combines all methods from both test_lifecycle.py and test_orchestrator.py
    versions into a single shared implementation.
    """

    def __init__(self):
        self.tools: dict[str, dict] = {}
        self.status_updates: list[tuple[str, str]] = []
        self.usage_records: list[str] = []

    def get_tool(self, tool_id: str) -> dict | None:
        return self.tools.get(tool_id)

    def list_tools(self, status: str | None = None) -> list[dict]:
        if status:
            return [t for t in self.tools.values() if t.get("status") == status]
        return list(self.tools.values())

    def add_tool(self, tool_info: dict) -> str:
        """Add a tool to the catalog. Returns the tool ID."""
        tid = tool_info.get("id") or tool_info.get("name", "unknown")
        self.tools[tid] = dict(tool_info)
        self.tools[tid]["id"] = tid
        self.tools[tid].setdefault("status", "discovered")
        return tid

    def update_status(self, tool_id: str, status: str):
        if tool_id in self.tools:
            self.tools[tool_id]["status"] = status
        self.status_updates.append((tool_id, status))

    def record_usage(self, tool_id: str):
        self.usage_records.append(tool_id)

    def search_tools(self, query: str = "", status: str | None = None, limit: int = 20) -> list[dict]:
        tools = self.list_tools(status)
        if not query:
            return tools[:limit]
        query_lower = query.lower()
        filtered = [
            t
            for t in tools
            if query_lower in t.get("name", "").lower() or query_lower in t.get("description", "").lower()
        ]
        return filtered[:limit]

    def count_by_status(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for t in self.tools.values():
            s = t.get("status", "unknown")
            counts[s] = counts.get(s, 0) + 1
        return counts

    def close(self):
        pass


@pytest.fixture
def fake_tool_catalog() -> FakeToolCatalog:
    """Return a fresh FakeToolCatalog instance."""
    return FakeToolCatalog()
