from unittest.mock import patch

from ecos.workflow.backend_registry import BackendResolutionError, resolve
from ecos.workflow.executor import execute_m1_workflow
from ecos.workflow.mesh_contract import is_silent_mock, run_metadata


def test_run_metadata_uses_caller_run_id_as_trace_id():
    metadata = run_metadata("交付检查", workflow_run_id="run-123")
    assert metadata["workflow_run_id"] == "run-123"
    assert metadata["trace_id"] == "run-123"


def test_explicit_unknown_backend_fails_closed():
    try:
        resolve({"execution": {"backend": "missing-backend"}})
    except BackendResolutionError as exc:
        assert "missing-backend" in str(exc)
    else:
        raise AssertionError("unknown explicit backend must not fall back")


def test_silent_mock_is_detected_recursively():
    assert is_silent_mock({"steps": [{"result": {"mode": "mock"}}]})
    assert not is_silent_mock({"steps": [{"result": {"mode": "real"}}]})


def test_executor_blocks_mock_success_and_emits_mesh_events():
    workflow = {
        "name": "mesh-test",
        "steps": [{"name": "step", "action": "run"}],
        "execution": {"backend": "custom"},
    }
    events = []
    with (
        patch("ecos.workflow.executor.load_workflow", return_value=workflow),
        patch("ecos.workflow.executor.validate_workflow", return_value=[]),
        patch("ecos.workflow.executor.resolve", return_value=lambda *_: {
            "steps": [{"name": "step", "status": "ok", "result": {"mode": "mock"}}],
            "passed": 1,
            "failed": 0,
        }),
    ):
        result = execute_m1_workflow(
            "mesh-test",
            params={"workflow_run_id": "run-mesh-test", "event_sink": events.append},
        )

    assert result["run_metadata"]["workflow_run_id"] == "run-mesh-test"
    assert result["run_metadata"]["state"] == "unavailable"
    assert result["error_code"] == "SILENT_MOCK_BLOCKED"
    event_types = [event["event_type"] for event in events]
    assert event_types[0] == "WorkflowRequested"
    assert event_types[-1] == "BackendUnavailable"
    assert {"WorkflowAdmitted", "StepDispatched", "StepStarted"}.issubset(event_types)
    assert len({event["idempotency_key"] for event in events}) == len(events)
