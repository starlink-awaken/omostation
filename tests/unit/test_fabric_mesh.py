"""Unit tests for omlxc Local Edge Mesh & Compute Roaming Router (ADR-0202)."""

import pytest

from omlxc.mesh import MeshDiscoveryEngine, MeshNodeInfo, RoamingComputeRouter


def test_mesh_discovery_ranking():
    """Verify discovery engine sorts nodes by health, free VRAM, and latency."""
    engine = MeshDiscoveryEngine(local_node_id="node-laptop")
    node_laptop = MeshNodeInfo(
        node_id="node-laptop",
        host="192.168.1.10",
        vram_total_gb=16.0,
        vram_free_gb=2.0,
        thermal_pressure="serious",  # 节流
        latency_ms=0.5,
    )
    node_studio = MeshNodeInfo(
        node_id="node-studio",
        host="192.168.1.50",
        vram_total_gb=64.0,
        vram_free_gb=48.0,
        thermal_pressure="nominal",
        loaded_models=["qwen-32b", "deepseek-r1-7b"],
        latency_ms=1.2,
    )

    engine.register_peer(node_laptop)
    engine.register_peer(node_studio)

    nodes = engine.list_active_nodes()
    assert len(nodes) == 2
    # Studio 节点健康且显存大，排在最前
    assert nodes[0].node_id == "node-studio"

    best = engine.find_best_placement("qwen-32b", priority="P0")
    assert best is not None
    assert best.node_id == "node-studio"


def test_roaming_router_local_execution():
    """Verify job executes locally when local node has adequate resources."""
    engine = MeshDiscoveryEngine(local_node_id="node-local")
    local = MeshNodeInfo(
        node_id="node-local",
        host="localhost",
        vram_total_gb=32.0,
        vram_free_gb=20.0,
        thermal_pressure="nominal",
    )
    engine.register_peer(local)

    router = RoamingComputeRouter(discovery_engine=engine, local_node_id="node-local")
    decision = router.route_job("job-001", model_id="llama3-8b", estimated_vram_gb=5.0)

    assert decision.is_roamed is False
    assert decision.target_node_id == "node-local"
    assert "本地节点资源充足" in decision.decision_reason


def test_roaming_router_spillover_on_thermal_pressure():
    """Verify job roams to remote studio node when local node is thermally throttled."""
    engine = MeshDiscoveryEngine(local_node_id="node-local")
    local_hot = MeshNodeInfo(
        node_id="node-local",
        host="127.0.0.1",
        vram_total_gb=32.0,
        vram_free_gb=10.0,
        thermal_pressure="critical",  # 高温严重节流
    )
    remote_studio = MeshNodeInfo(
        node_id="node-studio",
        host="192.168.1.200",
        vram_total_gb=64.0,
        vram_free_gb=50.0,
        thermal_pressure="nominal",
    )
    engine.register_peer(local_hot)
    engine.register_peer(remote_studio)

    router = RoamingComputeRouter(discovery_engine=engine, local_node_id="node-local")
    decision = router.route_job("job-002", model_id="deepseek-r1", priority="P0")

    assert decision.is_roamed is True
    assert decision.target_node_id == "node-studio"
    assert decision.target_endpoint == "192.168.1.200:8765"
    assert "温度节流" in decision.decision_reason
