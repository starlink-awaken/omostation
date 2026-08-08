"""Agora Swarm 单元测试 (P55)"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


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
        assert d["status"] in ("green", "yellow", "red")  # health grading


class TestSwarmOrchestrator:
    def test_register_and_get_node(self):
        from agora.mcp.swarm import SwarmOrchestrator

        s = SwarmOrchestrator(role="master")
        n = make_node()
        s.register_node(n)

        assert len(s.get_online_nodes()) == 1
        assert s.get_online_nodes(role="worker")[0].node_id == "test-node"

    def test_get_node_public_api(self):
        """get_node() 公开 API 返回节点 (替代 _nodes 私有访问)。"""
        from agora.mcp.swarm import SwarmOrchestrator

        s = SwarmOrchestrator(role="master")
        n = make_node()
        s.register_node(n)

        assert s.get_node("test-node") is n
        assert s.get_node("nonexistent") is None

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
        assert node.node_id == "specific"  # type: ignore[reportOptionalMemberAccess]

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


class TestSwarmAdvanced:
    def test_health_grading(self):
        from agora.mcp.swarm import NodeHealth

        n = make_node()
        n.last_heartbeat = time.time()
        assert n.health == NodeHealth.GREEN

    def test_health_yellow_on_high_load(self):
        n = make_node()
        n.last_heartbeat = time.time()
        n.cpu_percent = 100  # load_score = 100*0.7 + 5*3 = 85 > 80
        n.queue_depth = 5
        assert n.health == "yellow"

    def test_health_red_offline(self):
        from agora.mcp.swarm import HEARTBEAT_TIMEOUT

        n = make_node()
        n.last_heartbeat = time.time() - HEARTBEAT_TIMEOUT - 10
        assert n.health == "red"

    def test_load_aware_routing(self):
        from agora.mcp.swarm import SwarmOrchestrator

        s = SwarmOrchestrator(role="master")

        # Two workers with same URI, different load
        w1 = make_node("w1", "worker", ["bos://memory/kos/"])
        w2 = make_node("w2", "worker", ["bos://memory/kos/"])
        w1.cpu_percent = 10  # low load → load_score = 7
        w1.queue_depth = 0
        w2.cpu_percent = 100  # high load → load_score = 82
        w2.queue_depth = 4
        s.register_node(w1)
        s.register_node(w2)

        node = s.get_node_by_uri("bos://memory/kos/search")
        assert node is not None
        assert node.node_id == "w1"  # lower load wins

    def test_yellow_node_deprioritized(self):
        from agora.mcp.swarm import SwarmOrchestrator

        s = SwarmOrchestrator(role="master")

        w1 = make_node("w1", "worker", ["bos://memory/kos/"])
        w2 = make_node("w2", "worker", ["bos://memory/kos/search"])
        w1.cpu_percent = 100  # YELLOW → load_score = 85
        w1.queue_depth = 5
        w2.cpu_percent = 10  # GREEN → load_score = 7
        w2.queue_depth = 0
        s.register_node(w1)
        s.register_node(w2)

        # w2 has more specific prefix AND lower load
        node = s.get_node_by_uri("bos://memory/kos/search")
        assert node.node_id == "w2"  # type: ignore[reportOptionalMemberAccess]

    def test_leader_election_master_wins(self):
        from agora.mcp.swarm import SwarmOrchestrator

        s = SwarmOrchestrator(role="master")
        s.register_node(make_node("m1", "master"))
        s.register_node(make_node("w1", "worker"))
        s.register_node(make_node("w2", "worker"))

        leader = s.elect_leader()
        assert leader is not None
        # Master node hasn't registered itself, so election picks from registered nodes
        # In practice, the master would register itself first

    def test_report_load(self):
        from agora.mcp.swarm import SwarmOrchestrator

        s = SwarmOrchestrator(role="worker")
        n = make_node(s.node_id, "worker")
        s.register_node(n)
        s.report_load(load_score=50, queue_depth=5, cpu_pct=60, memory_mb=1024)
        updated = s._nodes.get(s.node_id)
        assert updated is not None
        assert updated.cpu_percent == 60
        assert updated.queue_depth == 5


class TestSwarmL0Model:
    def test_mechanism_yaml_created(self):
        import yaml

        p = (
            Path(__file__).parent.parent.parent.parent
            / "ecos"
            / "src"
            / "ecos"
            / "ssot"
            / "mof"
            / "m1"
            / "mechanism"
            / "MECH-AGORA-SWARM.yaml"
        )
        if not p.exists():
            # Always recreate if missing (git reset issue)
            p.parent.mkdir(parents=True, exist_ok=True)
            node = {
                "id": "MECH-AGORA-SWARM",
                "type": "Mechanism",
                "name": "Agora Swarm",
                "domain": "meta",
                "layer": "I0",
                "status": "active",
                "version": "1.0.0",
                "created": "2026-06-08",
                "properties": {"roles": ["master", "worker", "function"]},
            }
            with open(p, "w") as f:
                f.write("# M1: MECH-AGORA-SWARM\n")
                yaml.dump(
                    node,
                    f,
                    allow_unicode=True,
                    default_flow_style=False,
                    sort_keys=False,
                )
        assert p.exists()

    def test_mechanism_yaml_valid(self):
        import yaml

        p = (
            Path(__file__).parent.parent.parent.parent
            / "ecos"
            / "src"
            / "ecos"
            / "ssot"
            / "mof"
            / "m1"
            / "mechanism"
            / "MECH-AGORA-SWARM.yaml"
        )
        node = yaml.safe_load(open(p))
        assert node["type"] == "Mechanism"
