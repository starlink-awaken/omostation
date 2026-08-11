from __future__ import annotations

from dataclasses import replace

import pytest

from omlxc.domain import RouteProfile, RouteRequest
from omlxc.scheduler import (
    PlacementSnapshot,
    RejectionCode,
    RouteFailure,
    RouteFailureCode,
    RoutePlanner,
    default_policies,
)


def _request(**updates: object) -> RouteRequest:
    values: dict[str, object] = {
        "request_id": "req-1",
        "model_id": "local/model",
        "profile": RouteProfile.INTERACTIVE,
        "required_capabilities": frozenset({"chat"}),
        "context_tokens": 1024,
    }
    values.update(updates)
    return RouteRequest.model_validate(values)


def _placement(placement_id: str, **updates: object) -> PlacementSnapshot:
    values: dict[str, object] = {
        "placement_id": placement_id,
        "model_id": "local/model",
        "backend_id": f"backend-{placement_id}",
        "backend_model_id": f"physical-{placement_id}",
        "node_id": f"node-{placement_id}",
        "fresh": True,
        "available": True,
        "authorized": True,
        "capabilities": frozenset({"chat", "vision", "embedding"}),
        "context_limit": 8192,
        "memory_admitted": True,
        "loaded": False,
        "ttft_ms": 500.0,
        "throughput_tps": 30.0,
        "queue_depth": 1,
        "error_rate": 0.01,
        "network_cost_ms": 5.0,
        "affinity": 0.5,
        "available_concurrency": 1,
        "local": True,
        "security_allowed": True,
    }
    values.update(updates)
    return PlacementSnapshot(**values)


def test_profiles_are_validated_and_drive_different_priorities() -> None:
    policies = default_policies()
    assert set(policies) == set(RouteProfile)
    assert (
        policies[RouteProfile.INTERACTIVE].weights.ttft > policies[RouteProfile.BATCH].weights.ttft
    )
    assert (
        policies[RouteProfile.BATCH].weights.throughput
        > policies[RouteProfile.INTERACTIVE].weights.throughput
    )


def test_filter_order_rejections_and_local_only_are_deterministic() -> None:
    placements = (
        _placement("wrong-model", model_id="other"),
        _placement("stale", fresh=False, capabilities=frozenset()),
        _placement("capability", capabilities=frozenset()),
        _placement("context", context_limit=128),
        _placement("memory", memory_admitted=False),
        _placement("capacity", available_concurrency=0),
        _placement("cloud", local=False),
        _placement("good"),
    )

    first = RoutePlanner(default_policies()).plan(_request(), placements)
    second = RoutePlanner(default_policies()).plan(_request(), tuple(reversed(placements)))

    assert first == second
    assert first.selected_placement_id == "good"
    assert first.rejected == {
        "capacity": RejectionCode.NO_CAPACITY.value,
        "capability": RejectionCode.CAPABILITY.value,
        "cloud": RejectionCode.LOCAL_SECURITY.value,
        "context": RejectionCode.CONTEXT.value,
        "memory": RejectionCode.MEMORY.value,
        "stale": RejectionCode.HEALTH.value,
        "wrong-model": RejectionCode.MODEL.value,
    }
    assert "cloud" not in first.candidates
    assert "selected=good" in first.explanation


def test_scoring_covers_required_dimensions_and_ties_by_placement_id() -> None:
    baseline = _placement("z")
    improvements = {
        "loaded": True,
        "ttft_ms": 1.0,
        "throughput_tps": 200.0,
        "queue_depth": 0,
        "error_rate": 0.0,
        "network_cost_ms": 0.0,
        "affinity": 1.0,
    }
    for field, value in improvements.items():
        better = replace(baseline, placement_id="a", **{field: value})
        decision = RoutePlanner(default_policies()).plan(_request(), (baseline, better))
        assert decision.selected_placement_id == "a", field

    tied = RoutePlanner(default_policies()).plan(_request(), (_placement("z"), _placement("a")))
    assert tied.candidates == ("a", "z")
    assert tuple(tied.candidate_scores) == ("a", "z")


def test_unknown_critical_values_fail_closed_and_performance_defaults_are_explicit() -> None:
    rejected = RoutePlanner(default_policies()).plan(
        _request(), (_placement("unknown", available_concurrency=None),)
    )
    assert isinstance(rejected, RouteFailure)
    assert rejected.code is RouteFailureCode.NO_CAPACITY

    defaulted = _placement(
        "defaulted",
        ttft_ms=None,
        throughput_tps=None,
        queue_depth=None,
        error_rate=None,
        network_cost_ms=None,
        affinity=None,
    )
    decision = RoutePlanner(default_policies()).plan(_request(), (defaulted,))
    assert decision.selected_placement_id == "defaulted"
    assert "defaults=" in decision.explanation


def test_non_finite_and_out_of_range_snapshot_values_are_rejected() -> None:
    with pytest.raises(ValueError):
        _placement("bad", ttft_ms=float("nan"))
    with pytest.raises(ValueError):
        _placement("bad", error_rate=1.1)


def test_duplicate_placement_ids_fail_closed_before_scoring() -> None:
    result = RoutePlanner(default_policies()).plan(
        _request(), (_placement("duplicate"), _placement("duplicate"))
    )
    assert isinstance(result, RouteFailure)
    assert result.code is RouteFailureCode.INVALID_SNAPSHOT
