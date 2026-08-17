"""
Priority Quality-of-Service (QoS) and Headroom Reservation for omlxc.

Defines 3-tier request priorities:
- P0_INTERACTIVE: Human developer & IDE single-step queries (zero-wait preemption headroom)
- P1_AUTONOMOUS: Active autonomous coding agents (OpenCode, AetherForge, Kilo)
- P2_BATCH: Background documentation indexing, off-peak sweeps, and benchmark runs
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import Final


class RequestPriority(enum.StrEnum):
    """Scheduling priority class."""

    P0_INTERACTIVE = "p0_interactive"
    P1_AUTONOMOUS = "p1_autonomous"
    P2_BATCH = "p2_batch"


@dataclass(frozen=True, slots=True)
class PriorityPolicy:
    """Reservation and preemption policy rules."""

    interactive_headroom_slots: int = 1
    p2_max_concurrency_ratio: float = 0.5  # P2 cannot consume more than 50% node slots
    p0_score_boost: float = 1.25
    p2_busy_penalty: float = 0.6


DEFAULT_PRIORITY_POLICY: Final[PriorityPolicy] = PriorityPolicy()


def compute_priority_multiplier(
    priority: RequestPriority,
    in_flight: int,
    max_concurrency: int,
    policy: PriorityPolicy = DEFAULT_PRIORITY_POLICY,
) -> float:
    """
    Compute score multiplier based on request priority and node utilization.

    Protects interactive headroom and throttles background batch tasks during high load.
    """
    available_slots = max(max_concurrency - in_flight, 0)

    if priority == RequestPriority.P0_INTERACTIVE:
        # P0 gets bonus and can utilize reserved headroom
        return policy.p0_score_boost

    if priority == RequestPriority.P1_AUTONOMOUS:
        # P1 cannot consume the last reserved slot on primary node if headroom > 0
        if available_slots <= policy.interactive_headroom_slots and max_concurrency > 1:
            return 0.7
        return 1.0

    # P2_BATCH
    if available_slots <= policy.interactive_headroom_slots:
        return 0.1  # Strongly penalize batch tasks when headroom is constrained
    if in_flight >= int(max_concurrency * policy.p2_max_concurrency_ratio):
        return policy.p2_busy_penalty
    return 0.9
