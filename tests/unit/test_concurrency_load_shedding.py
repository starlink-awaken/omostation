"""
Unit tests for ConcurrencyTracker and in-flight load shedding.
"""

from __future__ import annotations

import pytest

from omlxc.dataplane.concurrency import ConcurrencyTracker
from omlxc.domain import RouteProfile, RouteRequest
from omlxc.scheduler.models import PlacementSnapshot, RejectionCode, default_policies
from omlxc.scheduler.planner import RoutePlanner


def _snapshot(placement_id: str, in_flight: int = 0, max_concurrency: int = 4) -> PlacementSnapshot:
    return PlacementSnapshot(
        placement_id=placement_id,
        model_id="coding",
        backend_id="mlx",
        backend_model_id="coding",
        node_id="local-node",
        fresh=True,
        available=True,
        authorized=True,
        capabilities=frozenset({"chat"}),
        context_limit=32768,
        memory_admitted=True,
        loaded=True,
        ttft_ms=20.0,
        throughput_tps=50.0,
        queue_depth=0,
        error_rate=0.0,
        network_cost_ms=0.0,
        affinity=1.0,
        available_concurrency=4,
        local=True,
        security_allowed=True,
        circuit_open=False,
        in_flight=in_flight,
        max_concurrency=max_concurrency,
    )


@pytest.mark.asyncio
async def test_concurrency_tracker_acquire_release() -> None:
    tracker = ConcurrencyTracker(default_max_concurrency=2)
    assert tracker.get_in_flight("p-1") == 0
    assert not tracker.is_overloaded("p-1")

    async with tracker.track("p-1") as count1:
        assert count1 == 1
        assert tracker.get_in_flight("p-1") == 1

        async with tracker.track("p-1") as count2:
            assert count2 == 2
            assert tracker.is_overloaded("p-1")

    assert tracker.get_in_flight("p-1") == 0
    assert not tracker.is_overloaded("p-1")


def test_planner_overflows_when_first_node_at_concurrency_limit() -> None:
    planner = RoutePlanner(default_policies())
    req = RouteRequest(
        request_id="req-1",
        model_id="coding",
        profile=RouteProfile.INTERACTIVE,
        context_tokens=1000,
        required_capabilities=frozenset({"chat"}),
        thinking_requested=False,
    )

    # Node A is at max concurrency (4/4), Node B has 0 in-flight (0/4)
    node_a = _snapshot("placement-a", in_flight=4, max_concurrency=4)
    node_b = _snapshot("placement-b", in_flight=0, max_concurrency=4)

    decision = planner.plan(req, (node_a, node_b))
    assert decision.selected_placement_id == "placement-b"
    assert decision.rejected.get("placement-a") == RejectionCode.CONCURRENCY_LIMIT.value
