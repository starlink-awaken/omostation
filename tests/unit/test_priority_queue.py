"""Unit tests for Priority QoS and headroom reservation."""

from __future__ import annotations

from omlxc.scheduler.priority import (
    DEFAULT_PRIORITY_POLICY,
    PriorityPolicy,
    RequestPriority,
    compute_priority_multiplier,
)


def test_priority_multiplier_interactive_p0() -> None:
    # P0 always receives boost regardless of in-flight count
    mult_idle = compute_priority_multiplier(
        RequestPriority.P0_INTERACTIVE, in_flight=0, max_concurrency=4
    )
    assert mult_idle == DEFAULT_PRIORITY_POLICY.p0_score_boost

    mult_busy = compute_priority_multiplier(
        RequestPriority.P0_INTERACTIVE, in_flight=3, max_concurrency=4
    )
    assert mult_busy == DEFAULT_PRIORITY_POLICY.p0_score_boost


def test_priority_multiplier_autonomous_p1() -> None:
    # P1 operates normally when ample slots exist
    mult_normal = compute_priority_multiplier(
        RequestPriority.P1_AUTONOMOUS, in_flight=1, max_concurrency=4
    )
    assert mult_normal == 1.0

    # P1 throttled when only reserved interactive headroom remains
    mult_headroom = compute_priority_multiplier(
        RequestPriority.P1_AUTONOMOUS, in_flight=3, max_concurrency=4
    )
    assert mult_headroom == 0.7


def test_priority_multiplier_batch_p2() -> None:
    policy = PriorityPolicy(interactive_headroom_slots=1, p2_max_concurrency_ratio=0.5)

    # Idle load
    mult_idle = compute_priority_multiplier(
        RequestPriority.P2_BATCH, in_flight=0, max_concurrency=4, policy=policy
    )
    assert mult_idle == 0.9

    # Exceeding 50% concurrency ratio (in_flight=2, max=4)
    mult_busy = compute_priority_multiplier(
        RequestPriority.P2_BATCH, in_flight=2, max_concurrency=4, policy=policy
    )
    assert mult_busy == policy.p2_busy_penalty

    # Only headroom remaining (in_flight=3, max=4)
    mult_locked = compute_priority_multiplier(
        RequestPriority.P2_BATCH, in_flight=3, max_concurrency=4, policy=policy
    )
    assert mult_locked == 0.1
