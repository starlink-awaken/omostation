from __future__ import annotations

from omlxc.domain import RouteProfile, RouteRequest
from omlxc.scheduler.models import (
    PlacementSnapshot,
    RejectionCode,
    default_policies,
)
from omlxc.scheduler.planner import RoutePlanner


def make_snapshot(
    placement_id: str,
    *,
    ttft_ms: float | None = 50.0,
    throughput_tps: float | None = 60.0,
    circuit_open: bool = False,
) -> PlacementSnapshot:
    return PlacementSnapshot(
        placement_id=placement_id,
        model_id="coding",
        backend_id="b1",
        backend_model_id="bm1",
        node_id="n1",
        fresh=True,
        available=True,
        authorized=True,
        capabilities=frozenset({"chat"}),
        context_limit=4096,
        memory_admitted=True,
        loaded=True,
        ttft_ms=ttft_ms,
        throughput_tps=throughput_tps,
        queue_depth=0,
        error_rate=0.0,
        network_cost_ms=1.0,
        affinity=1.0,
        available_concurrency=4,
        local=True,
        security_allowed=True,
        circuit_open=circuit_open,
    )


def test_dynamic_planner_prefers_higher_throughput_and_lower_ttft() -> None:
    planner = RoutePlanner(default_policies())

    req = RouteRequest(
        request_id="req-1",
        model_id="coding",
        profile=RouteProfile.INTERACTIVE,
        context_tokens=100,
        required_capabilities=frozenset({"chat"}),
        thinking_requested=False,
    )

    # Fast placement vs Slow placement
    p_fast = make_snapshot("p-fast", ttft_ms=20.0, throughput_tps=90.0)
    p_slow = make_snapshot("p-slow", ttft_ms=200.0, throughput_tps=25.0)

    decision = planner.plan(req, [p_slow, p_fast])
    assert hasattr(decision, "selected_placement_id")
    assert decision.selected_placement_id == "p-fast"
    assert decision.candidate_scores["p-fast"] > decision.candidate_scores["p-slow"]


def test_dynamic_planner_rejects_circuit_open_placement() -> None:
    planner = RoutePlanner(default_policies())

    req = RouteRequest(
        request_id="req-1",
        model_id="coding",
        profile=RouteProfile.INTERACTIVE,
        context_tokens=100,
        required_capabilities=frozenset({"chat"}),
        thinking_requested=False,
    )

    p_broken = make_snapshot("p-broken", circuit_open=True)
    p_healthy = make_snapshot("p-healthy", ttft_ms=100.0, throughput_tps=30.0)

    decision = planner.plan(req, [p_broken, p_healthy])
    assert decision.selected_placement_id == "p-healthy"
    assert "p-broken" in decision.rejected
    assert decision.rejected["p-broken"] == RejectionCode.CIRCUIT_OPEN.value
