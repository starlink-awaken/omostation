"""
Unit tests for Last-Resort Emergency Probing when all candidate placements are in circuit_open.
"""

from __future__ import annotations

from omlxc.domain import RouteProfile, RouteRequest
from omlxc.scheduler.models import PlacementSnapshot, default_policies
from omlxc.scheduler.planner import RoutePlanner


def _circuit_open_snapshot(placement_id: str, throughput: float) -> PlacementSnapshot:
    return PlacementSnapshot(
        placement_id=placement_id,
        model_id="coding",
        backend_id="mlx",
        backend_model_id="coding",
        node_id="node-1",
        fresh=True,
        available=True,
        authorized=True,
        capabilities=frozenset({"chat"}),
        context_limit=32768,
        memory_admitted=True,
        loaded=True,
        ttft_ms=20.0,
        throughput_tps=throughput,
        queue_depth=0,
        error_rate=0.0,
        network_cost_ms=0.0,
        affinity=1.0,
        available_concurrency=4,
        local=True,
        security_allowed=True,
        circuit_open=True,  # All in circuit_open!
    )


def test_last_resort_probe_picks_highest_scoring_candidate_instead_of_failing() -> None:
    planner = RoutePlanner(default_policies())
    req = RouteRequest(
        request_id="req-emergency",
        model_id="coding",
        profile=RouteProfile.BATCH,
        context_tokens=100,
        required_capabilities=frozenset({"chat"}),
        thinking_requested=False,
    )

    # Both nodes in circuit_open; Node B has higher throughput
    node_a = _circuit_open_snapshot("placement-a", throughput=25.0)
    node_b = _circuit_open_snapshot("placement-b", throughput=65.0)

    decision = planner.plan(req, (node_a, node_b))
    assert decision.selected_placement_id == "placement-b"
    assert "last_resort_probing=true" in decision.explanation
