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
        "BackendAdapterV1",
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
