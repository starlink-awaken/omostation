"""Unit tests for RoutePlanner thermal penalty and triage scheduling."""

from __future__ import annotations

from omlxc.domain import RouteProfile, RouteRequest
from omlxc.scheduler.models import PlacementSnapshot, default_policies
from omlxc.scheduler.planner import RoutePlanner


def _make_snapshot(
    placement_id: str,
    thermal_penalty: float = 1.0,
    ttft_ms: float = 20.0,
    throughput_tps: float = 50.0,
) -> PlacementSnapshot:
    return PlacementSnapshot(
        placement_id=placement_id,
        model_id="coding",
        backend_id="omlx_app",
        backend_model_id="qwen-27b",
        node_id="node-1",
        fresh=True,
        available=True,
        authorized=True,
        capabilities=frozenset({"chat"}),
        context_limit=16384,
        memory_admitted=True,
        loaded=True,
        ttft_ms=ttft_ms,
        throughput_tps=throughput_tps,
        queue_depth=0,
        error_rate=0.0,
        network_cost_ms=0.0,
        affinity=1.0,
        available_concurrency=4,
        local=True,
        security_allowed=True,
        thermal_penalty=thermal_penalty,
    )


def test_planner_applies_thermal_penalty() -> None:
    planner = RoutePlanner(default_policies())

    p_hot = _make_snapshot("placement-mbp-hot", thermal_penalty=0.5)
    p_cool = _make_snapshot("placement-mini-cool", thermal_penalty=1.0, ttft_ms=30.0)

    req = RouteRequest(
        request_id="req-1",
        model_id="coding",
        profile=RouteProfile.INTERACTIVE,
        context_tokens=1000,
        required_capabilities=frozenset({"chat"}),
        thinking_requested=False,
    )

    decision = planner.plan(req, (p_hot, p_cool))
    assert decision.selected_placement_id == "placement-mini-cool"
    score_cool = decision.candidate_scores["placement-mini-cool"]
    score_hot = decision.candidate_scores["placement-mbp-hot"]
    assert score_cool > score_hot
