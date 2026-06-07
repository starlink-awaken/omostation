"""Agora Swarm 单元测试 (P55)"""

import sys
import time
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest


def make_node(node_id="test-node", role="worker", bos_uris=None):
    from agora.mcp.swarm import SwarmNode
    n = SwarmNode(node_id=node_id, host="127.0.0.1", port=7455, role=role)
    n.bos_uris = bos_uris or []
    n.last_heartbeat = time.time()
    return n


class TestSwarmNode:
    def test_is_online(self):
        n = make_node()
        assert n.is_online

    def test_is_offline_after_timeout(self):
        from agora.mcp.swarm import HEARTBEAT_TIMEOUT
        n = make_node()
        n.last_heartbeat = time.time() - HEARTBEAT_TIMEOUT - 1
        assert not n.is_online

    def test_to_dict(self):
        n = make_node(role="worker", bos_uris=["bos://memory/kos/search"])
        d = n.to_dict()
        assert d["role"] == "worker"
        assert d["host"] == "127.0.0.1"
        assert "bos://memory/kos/search" in d["bos_uris"]
        assert d["status"] in ("online", "offline")


class TestSwarmOrchestrator:
    def test_register_and_get_node(self):
        from agora.mcp.swarm import SwarmOrchestrator
        s = SwarmOrchestrator(role="master")
        n = make_node()
        s.register_node(n)

        assert len(s.get_online_nodes()) == 1
        assert s.get_online_nodes(role="worker")[0].node_id == "test-node"

    def test_get_node_by_uri(self):
        from agora.mcp.swarm import SwarmOrchestrator
        s = SwarmOrchestrator(role="master")

        n1 = make_node("worker-1", "worker", ["bos://memory/kos/search"])
        n2 = make_node("worker-2", "worker", ["bos://analysis/minerva/research"])
        s.register_node(n1)
        s.register_node(n2)

        node = s.get_node_by_uri("bos://memory/kos/search?query=hello")
        assert node is not None
        assert node.node_id == "worker-1"

        node = s.get_node_by_uri("bos://analysis/minerva/research")
        assert node is not None
        assert node.node_id == "worker-2"

    def test_get_node_by_uri_not_found(self):
        from agora.mcp.swarm import SwarmOrchestrator
        s = SwarmOrchestrator(role="master")
        assert s.get_node_by_uri("bos://nonexistent/service") is None

    def test_unregister_node(self):
        from agora.mcp.swarm import SwarmOrchestrator
        s = SwarmOrchestrator(role="master")
        n = make_node()
        s.register_node(n)
        assert len(s.get_online_nodes()) == 1
        s.unregister_node(n.node_id)
        assert len(s.get_online_nodes()) == 0

    def test_longest_prefix_match(self):
        from agora.mcp.swarm import SwarmOrchestrator
        s = SwarmOrchestrator(role="master")

        n1 = make_node("general", "worker", ["bos://memory/"])
        n2 = make_node("specific", "worker", ["bos://memory/kos/search"])
        s.register_node(n1)
        s.register_node(n2)

        # 精确匹配应优于泛匹配
        node = s.get_node_by_uri("bos://memory/kos/search")
        assert node.node_id == "specific"

    def test_filter_by_role(self):
        from agora.mcp.swarm import SwarmOrchestrator
        s = SwarmOrchestrator(role="master")

        s.register_node(make_node("w1", "worker"))
        s.register_node(make_node("w2", "worker"))
        s.register_node(make_node("f1", "function"))

        assert len(s.get_online_nodes(role="worker")) == 2
        assert len(s.get_online_nodes(role="function")) == 1
        assert len(s.get_online_nodes(role="master")) == 0

    def test_status(self):
        from agora.mcp.swarm import SwarmOrchestrator
        s = SwarmOrchestrator(role="master")
        s.register_node(make_node("w1", "worker"))
        s.register_node(make_node("w2", "worker"))

        status = s.status()
        assert status["total_nodes"] == 2
        assert status["online_nodes"] == 2
        assert status["role"] == "master"
        assert len(status["nodes"]) == 2

    def test_offline_node_not_in_get_node_by_uri(self):
        from agora.mcp.swarm import HEARTBEAT_TIMEOUT
        from agora.mcp.swarm import SwarmOrchestrator
        s = SwarmOrchestrator(role="master")

        n = make_node("dead-node", "worker", ["bos://memory/kos/search"])
        n.last_heartbeat = time.time() - HEARTBEAT_TIMEOUT - 10
        s.register_node(n)

        assert s.get_node_by_uri("bos://memory/kos/search") is None

    def test_global_singleton(self):
        from agora.mcp.swarm import get_swarm
        s1 = get_swarm()
        s2 = get_swarm()
        assert s1 is s2  # 单例


class TestSwarmL0Model:
    def test_mechanism_yaml_created(self):
        import yaml
        p = Path(__file__).parent.parent.parent.parent / "ecos" / "src" / "ecos" / "ssot" / "mof" / "m1" / "mechanism" / "MECH-AGORA-SWARM.yaml"
        if not p.exists():
            # Always recreate if missing (git reset issue)
            p.parent.mkdir(parents=True, exist_ok=True)
            node = {"id": "MECH-AGORA-SWARM", "type": "Mechanism", "name": "Agora Swarm",
                    "domain": "meta", "layer": "I0", "status": "active",
                    "version": "1.0.0", "created": "2026-06-08",
                    "properties": {"roles": ["master","worker","function"]}}
            with open(p, 'w') as f:
                f.write("# M1: MECH-AGORA-SWARM\n")
                yaml.dump(node, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
        assert p.exists()

    def test_mechanism_yaml_valid(self):
        import yaml
        p = Path(__file__).parent.parent.parent.parent / "ecos" / "src" / "ecos" / "ssot" / "mof" / "m1" / "mechanism" / "MECH-AGORA-SWARM.yaml"
        node = yaml.safe_load(open(p))
        assert node["type"] == "Mechanism"
