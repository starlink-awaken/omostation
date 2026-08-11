"""Reusable, backend-neutral adapter protocol contracts."""

from __future__ import annotations

import importlib
from datetime import datetime

import pytest
from pydantic import ValidationError

from omlxc.domain.protocols import (
    AdapterError,
    AdapterErrorCode,
    CapabilitySnapshot,
    EmbeddingResult,
    LifecycleResult,
    ModelRuntime,
    ModelRuntimeState,
    OperationStatus,
    StreamEvent,
    StreamEventKind,
    StreamPhase,
    TuneResult,
    TuneScope,
)


def test_backend_protocol_exposes_typed_capability_and_stream_contracts() -> None:
    protocols = importlib.import_module("omlxc.domain.protocols")

    expected = {
        "AdapterError",
        "AdapterErrorCode",
        "BackendAdapter",
        "CapabilitySnapshot",
        "ChatRequest",
        "ChatResult",
        "EmbeddingRequest",
        "EmbeddingResult",
        "LifecycleResult",
        "ModelRuntime",
        "StreamEvent",
        "TuneRequest",
        "TuneResult",
    }

    assert expected <= set(vars(protocols))
    assert "BackendAdapterV1" not in vars(protocols)


def test_domain_exports_the_same_canonical_backend_protocol_object() -> None:
    from omlxc.domain import BackendAdapter as public_protocol
    from omlxc.domain.adapters import BackendAdapter as compatibility_protocol
    from omlxc.domain.protocols import BackendAdapter as canonical_protocol

    assert public_protocol is canonical_protocol
    assert compatibility_protocol is canonical_protocol


def test_generic_tune_settings_have_no_backend_specific_reasoning_knobs() -> None:
    from omlxc.domain.protocols import TuneSettings

    assert set(TuneSettings.model_fields) == {
        "max_context_window",
        "max_tokens",
        "temperature",
        "top_p",
        "ttl_seconds",
        "is_pinned",
    }


def test_model_runtime_preserves_unknown_loaded_state_as_none() -> None:
    unknown = ModelRuntime(
        id="model-a",
        state=ModelRuntimeState.UNKNOWN,
        loaded=None,
    )

    assert unknown.loaded is None
    with pytest.raises(ValidationError, match="loaded"):
        ModelRuntime(id="model-a", state=ModelRuntimeState.UNKNOWN, loaded=False)


def test_capability_snapshot_rejects_naive_observation_time() -> None:
    with pytest.raises(ValidationError, match="timezone"):
        CapabilitySnapshot(
            backend_id="backend-a",
            reachable=True,
            compatible=True,
            model_available=False,
            generation_ready=False,
            observed_at=datetime(2026, 8, 11),
        )


@pytest.mark.parametrize(
    ("model_type", "payload"),
    [
        (
            EmbeddingResult,
            {"request_id": "req-a", "status": OperationStatus.UNSUPPORTED},
        ),
        (
            LifecycleResult,
            {
                "model_id": "model-a",
                "status": OperationStatus.SUCCEEDED,
                "changed": False,
            },
        ),
        (
            TuneResult,
            {"scope": TuneScope.GLOBAL, "status": OperationStatus.UNSUPPORTED},
        ),
        (
            StreamEvent,
            {
                "kind": StreamEventKind.ERROR,
                "request_id": "req-a",
                "emitted_content": False,
                "phase": StreamPhase.BEFORE_CONTENT,
            },
        ),
    ],
)
def test_result_dtos_reject_internally_inconsistent_states(
    model_type: type[object], payload: dict[str, object]
) -> None:
    with pytest.raises(ValidationError):
        model_type.model_validate(payload)  # type: ignore[attr-defined]


def test_stream_error_requires_matching_replay_phase() -> None:
    error = AdapterError(
        code=AdapterErrorCode.STREAM_INTERRUPTED,
        message="interrupted",
        emitted_content=True,
        phase=StreamPhase.AFTER_CONTENT,
    )

    with pytest.raises(ValidationError, match="replay"):
        StreamEvent(
            kind=StreamEventKind.ERROR,
            request_id="req-a",
            error=error,
            emitted_content=False,
            phase=StreamPhase.BEFORE_CONTENT,
        )
