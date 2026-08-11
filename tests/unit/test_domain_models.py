"""Executable contracts for the pure omlxc domain layer."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from omlxc.domain import (
    EXIT_CAPACITY,
    EXIT_CONFIG,
    EXIT_DAEMON,
    EXIT_INTERNAL,
    EXIT_PARTIAL,
    EXIT_SECURITY,
    EXIT_SUCCESS,
    EXIT_TIMEOUT,
    BackendInstance,
    BackendKind,
    ErrorEnvelope,
    HealthSnapshot,
    Job,
    JobState,
    ModelSpec,
    Node,
    NodeState,
    Placement,
    RiskLevel,
    RouteDecision,
    RouteProfile,
    RouteRequest,
    error_exit_code,
    transition_job,
    transition_node,
)


def test_public_enums_and_exit_codes_are_stable() -> None:
    assert [state.value for state in NodeState] == [
        "unknown",
        "probing",
        "healthy",
        "degraded",
        "unreachable",
        "recovering",
    ]
    assert [state.value for state in JobState] == [
        "pending",
        "planning",
        "awaiting_confirmation",
        "running",
        "succeeded",
        "failed",
        "cancelling",
        "cancelled",
    ]
    assert [risk.value for risk in RiskLevel] == ["r0", "r1", "r2"]
    assert [profile.value for profile in RouteProfile] == [
        "interactive",
        "quality",
        "batch",
        "eco",
    ]
    assert [kind.value for kind in BackendKind] == [
        "omlx_app",
        "lm_studio",
        "lm_link",
        "ollama",
    ]
    assert {
        EXIT_SUCCESS,
        EXIT_CONFIG,
        EXIT_DAEMON,
        EXIT_CAPACITY,
        EXIT_TIMEOUT,
        EXIT_PARTIAL,
        EXIT_SECURITY,
        EXIT_INTERNAL,
    } == {0, 2, 3, 4, 5, 6, 7, 10}


def test_domain_entities_are_strict_frozen_and_json_serializable() -> None:
    observed_at = datetime(2026, 8, 11, tzinfo=UTC)
    health = HealthSnapshot(
        state=NodeState.HEALTHY,
        observed_at=observed_at,
        stale=False,
        detail="all probes passed",
    )
    node = Node(
        id="mbp-primary",
        display_name="Primary Mac",
        platform="macos",
        tailscale_identity="node.example.ts.net",
        control_endpoint="ssh://primary",
        inference_endpoints=("http://127.0.0.1:8000",),
        capabilities=frozenset({"chat", "embedding"}),
        memory_gb=64.0,
        health=health,
    )
    backend = BackendInstance(
        id="mbp-primary-omlx",
        node_id=node.id,
        kind=BackendKind.OMLX_APP,
        protocol_version="openai-v1",
        capabilities=frozenset({"chat", "stream"}),
        context_limit=32768,
        thinking_control="chat_template",
        streaming=True,
        controllable=True,
    )
    model = ModelSpec(
        id="model-a",
        role="chat",
        capabilities=frozenset({"chat"}),
        reasoning=False,
    )
    placement = Placement(
        id="model-a-on-mbp",
        model_id=model.id,
        backend_id=backend.id,
        backend_model_id="model-a",
        model_path="/redacted/model-a",
        context_limit=32768,
        quantization="4bit",
        memory_gb=8.0,
        resident=True,
        load_cost_seconds=2.5,
    )
    request = RouteRequest(
        request_id="req-1",
        model_id=model.id,
        profile=RouteProfile.INTERACTIVE,
        required_capabilities=frozenset({"chat"}),
        context_tokens=1024,
        thinking_requested=False,
    )
    decision = RouteDecision(
        request_id=request.request_id,
        selected_placement_id=placement.id,
        candidates=(placement.id,),
        rejected={},
        fallback_chain=(),
        config_version="1",
        explanation="only healthy candidate",
    )
    job = Job(
        id="job-1",
        kind="load_model",
        initiator="test",
        risk=RiskLevel.R1,
        state=JobState.PENDING,
        progress=0.0,
        created_at=observed_at,
        updated_at=observed_at,
    )

    assert node.model_dump(mode="json")["health"]["observed_at"] == "2026-08-11T00:00:00Z"
    assert decision.model_dump_json()
    assert job.model_dump_json()
    with pytest.raises(ValidationError, match="frozen"):
        node.display_name = "mutated"
    with pytest.raises(ValidationError):
        Placement(
            id="bad",
            model_id="model-a",
            backend_id="backend-a",
            backend_model_id="model-a",
            context_limit="32768",  # type: ignore[arg-type]
        )
    with pytest.raises(TypeError):
        decision.rejected["mutable"] = "not allowed"  # type: ignore[index]


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (NodeState.UNKNOWN, NodeState.PROBING),
        (NodeState.PROBING, NodeState.HEALTHY),
        (NodeState.PROBING, NodeState.DEGRADED),
        (NodeState.PROBING, NodeState.UNREACHABLE),
        (NodeState.UNREACHABLE, NodeState.RECOVERING),
        (NodeState.RECOVERING, NodeState.PROBING),
    ],
)
def test_node_state_machine_accepts_declared_transitions(
    current: NodeState, target: NodeState
) -> None:
    assert transition_node(current, target) is target


def test_node_state_machine_fails_closed_on_illegal_transition() -> None:
    with pytest.raises(ValueError, match="illegal node state transition"):
        transition_node(NodeState.HEALTHY, NodeState.RECOVERING)


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (JobState.PENDING, JobState.PLANNING),
        (JobState.PLANNING, JobState.AWAITING_CONFIRMATION),
        (JobState.PLANNING, JobState.RUNNING),
        (JobState.AWAITING_CONFIRMATION, JobState.RUNNING),
        (JobState.RUNNING, JobState.SUCCEEDED),
        (JobState.RUNNING, JobState.FAILED),
        (JobState.RUNNING, JobState.CANCELLING),
        (JobState.CANCELLING, JobState.CANCELLED),
    ],
)
def test_job_state_machine_accepts_declared_transitions(
    current: JobState, target: JobState
) -> None:
    assert transition_job(current, target) is target


def test_job_state_machine_fails_closed_on_illegal_transition() -> None:
    with pytest.raises(ValueError, match="illegal job state transition"):
        transition_job(JobState.SUCCEEDED, JobState.RUNNING)


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("E100", EXIT_CONFIG),
        ("E200", EXIT_DAEMON),
        ("E305", EXIT_TIMEOUT),
        ("E400", EXIT_CAPACITY),
        ("E500", EXIT_PARTIAL),
        ("E700", EXIT_SECURITY),
        ("E900", EXIT_INTERNAL),
    ],
)
def test_error_codes_map_to_the_public_exit_contract(code: str, expected: int) -> None:
    assert error_exit_code(code) == expected


def test_error_envelope_redacts_auth_material_and_is_frozen() -> None:
    error = ErrorEnvelope(
        code="E100",
        message="invalid token=top-secret",
        technical_detail="https://alice:hunter2@example.invalid api_key=abc123",
        suggested_action="set password=something-else",
        request_id="req-redaction",
        retryable=False,
        affected_resources=("Authorization: Bearer secret-bearer",),
        partial_result={"secret": "must-not-survive", "safe": "visible"},
    )
    serialized = error.model_dump_json()

    for sensitive in (
        "top-secret",
        "hunter2",
        "abc123",
        "something-else",
        "secret-bearer",
        "must-not-survive",
    ):
        assert sensitive not in serialized
    assert "visible" in serialized
    assert error.partial_result is not None
    with pytest.raises(TypeError):
        error.partial_result["safe"] = "mutated"  # type: ignore[index]
