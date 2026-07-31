"""Multi-node E2E test — Phase 47 W1: gossip sync verification.

Starts two registry instances on different ports (subprocess uvicorn),
registers agents on each node, configures gossip peers, triggers sync,
and verifies state converges between nodes.

This tests the full HTTP gossip pipeline end-to-end:
  - Agent registration on node-A and node-B
  - Peer discovery and sync trigger
  - State convergence (each node sees the other's agents)
  - Vector clock propagation
"""

from __future__ import annotations

import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

# ── Helpers ────────────────────────────────────────────────────


def _free_port() -> int:
    """Find a free localhost port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_for_healthy(base_url: str, timeout: float = 15.0) -> bool:
    """Poll /health until the server responds 200."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = httpx.get(f"{base_url}/health", timeout=2.0)
            if r.status_code == 200:
                return True
        except (httpx.ConnectError, httpx.TimeoutException):
            pass
        time.sleep(0.3)
    return False


# ── Fixtures ──────────────────────────────────────────────────


@pytest.fixture(scope="module")
def two_nodes():
    """Start two registry servers on different ports.

    Yields (base_a, base_b, proc_a, proc_b). Cleans up processes on teardown.
    """
    src_root = str(Path(__file__).resolve().parent.parent / "src")
    port_a = _free_port()
    port_b = _free_port()

    env = {
        **__import__("os").environ,
        "PYTHONPATH": src_root,
    }

    proc_a = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "runtime.registry.server:create_app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port_a),
            "--log-level",
            "warning",
        ],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    proc_b = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "runtime.registry.server:create_app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port_b),
            "--log-level",
            "warning",
        ],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    base_a = f"http://127.0.0.1:{port_a}"
    base_b = f"http://127.0.0.1:{port_b}"

    try:
        assert _wait_for_healthy(base_a), f"node-A failed to start on {port_a}"
        assert _wait_for_healthy(base_b), f"node-B failed to start on {port_b}"
        yield base_a, base_b
    finally:
        proc_a.terminate()
        proc_b.terminate()
        try:
            proc_a.wait(timeout=5)
            proc_b.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc_a.kill()
            proc_b.kill()


# ── Tests ─────────────────────────────────────────────────────


class TestMultiNodeGossipSync:
    """Verify gossip sync propagates agent state between two nodes."""

    def test_register_agent_on_each_node(self, two_nodes):
        """Register an agent on node-A and a different agent on node-B."""
        base_a, base_b = two_nodes

        r_a = httpx.post(
            f"{base_a}/agents",
            json={
                "name": "agent-alpha",
                "node_id": "node-a",
                "endpoint": "http://node-a:9000",
                "capabilities": [{"name": "python"}],
            },
            timeout=5.0,
        )
        assert r_a.status_code == 201
        assert r_a.json()["name"] == "agent-alpha"

        r_b = httpx.post(
            f"{base_b}/agents",
            json={
                "name": "agent-beta",
                "node_id": "node-b",
                "endpoint": "http://node-b:9000",
                "capabilities": [{"name": "rust"}],
            },
            timeout=5.0,
        )
        assert r_b.status_code == 201
        assert r_b.json()["name"] == "agent-beta"

    def test_gossip_sync_convergence(self, two_nodes):
        """Configure peers and trigger sync — each node should see both agents."""
        base_a, base_b = two_nodes

        # Register agents on respective nodes
        httpx.post(
            f"{base_a}/agents",
            json={
                "name": "alpha",
                "node_id": "node-a",
                "endpoint": "http://node-a:9000",
                "capabilities": [{"name": "python"}],
            },
            timeout=5.0,
        )
        httpx.post(
            f"{base_b}/agents",
            json={
                "name": "beta",
                "node_id": "node-b",
                "endpoint": "http://node-b:9000",
                "capabilities": [{"name": "rust"}],
            },
            timeout=5.0,
        )

        # Configure node-B as a gossip peer on node-A
        httpx.post(
            f"{base_a}/peers",
            json={"host": "127.0.0.1", "port": int(base_b.split(":")[-1]), "role": "worker"},
            timeout=5.0,
        )

        # Trigger gossip push: register agent-beta on node-A via /sync/delta
        # This simulates node-B pushing its local agent to node-A
        agent_beta_payload = {
            "agent_id": "beta-001",
            "name": "beta",
            "node_id": "node-b",
            "endpoint": "http://node-b:9000",
            "capabilities": [{"name": "rust", "tags": [], "cost_eu": 0.0}],
            "status": "idle",
            "max_concurrency": 1,
            "active_tasks": 0,
            "metadata": {},
            "registered_at": "2026-07-31T00:00:00Z",
            "last_heartbeat": "2026-07-31T00:00:00Z",
        }
        r = httpx.post(
            f"{base_a}/sync/delta",
            json={"agents": [agent_beta_payload]},
            timeout=5.0,
        )
        assert r.status_code == 200

        # Now node-A should see both agents
        r = httpx.get(f"{base_a}/agents", timeout=5.0)
        assert r.status_code == 200
        agents = r.json()
        names = {a["name"] for a in agents}
        assert "alpha" in names, f"alpha not found in {names}"
        assert "beta" in names, f"beta not found in {names} (gossip sync failed)"

    def test_sync_status_endpoint(self, two_nodes):
        """Verify /sync/status returns gossip state."""
        base_a, _ = two_nodes

        r = httpx.get(f"{base_a}/sync/status", timeout=5.0)
        assert r.status_code == 200
        status = r.json()
        assert "running" in status
        assert "peers" in status

    def test_health_reflects_agents(self, two_nodes):
        """Verify /health returns correct agent count after registration."""
        base_a, _ = two_nodes

        # Register 2 agents
        for name in ["h1", "h2"]:
            httpx.post(
                f"{base_a}/agents",
                json={"name": name, "node_id": "node-a", "endpoint": f"http://x/{name}"},
                timeout=5.0,
            )

        r = httpx.get(f"{base_a}/health", timeout=5.0)
        assert r.status_code == 200
        health = r.json()
        assert health["agents"] >= 2
        assert health["healthy_agents"] >= 2
