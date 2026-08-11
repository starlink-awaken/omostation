"""Fail-closed state transition rules."""

from __future__ import annotations

from .models import JobState, NodeState

_NODE_TRANSITIONS: dict[NodeState, frozenset[NodeState]] = {
    NodeState.UNKNOWN: frozenset({NodeState.PROBING}),
    NodeState.PROBING: frozenset({NodeState.HEALTHY, NodeState.DEGRADED, NodeState.UNREACHABLE}),
    NodeState.HEALTHY: frozenset({NodeState.PROBING, NodeState.DEGRADED, NodeState.UNREACHABLE}),
    NodeState.DEGRADED: frozenset({NodeState.PROBING, NodeState.HEALTHY, NodeState.UNREACHABLE}),
    NodeState.UNREACHABLE: frozenset({NodeState.RECOVERING}),
    NodeState.RECOVERING: frozenset({NodeState.PROBING, NodeState.UNREACHABLE}),
}

_JOB_TRANSITIONS: dict[JobState, frozenset[JobState]] = {
    JobState.PENDING: frozenset({JobState.PLANNING, JobState.CANCELLED}),
    JobState.PLANNING: frozenset(
        {JobState.AWAITING_CONFIRMATION, JobState.RUNNING, JobState.FAILED}
    ),
    JobState.AWAITING_CONFIRMATION: frozenset({JobState.RUNNING, JobState.CANCELLED}),
    JobState.RUNNING: frozenset({JobState.SUCCEEDED, JobState.FAILED, JobState.CANCELLING}),
    JobState.CANCELLING: frozenset({JobState.CANCELLED, JobState.FAILED}),
    JobState.SUCCEEDED: frozenset(),
    JobState.FAILED: frozenset(),
    JobState.CANCELLED: frozenset(),
}


def transition_node(current: NodeState, target: NodeState) -> NodeState:
    if target not in _NODE_TRANSITIONS[current]:
        raise ValueError(f"illegal node state transition: {current.value} -> {target.value}")
    return target


def transition_job(current: JobState, target: JobState) -> JobState:
    if target not in _JOB_TRANSITIONS[current]:
        raise ValueError(f"illegal job state transition: {current.value} -> {target.value}")
    return target
