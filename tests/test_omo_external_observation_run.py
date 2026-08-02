from __future__ import annotations

import pytest
from omo.omo_external_observation_run import (
    ExternalObservationRunError,
    read_external_observation_runs,
    record_external_observation_run,
)


def _payload(run_id: str = "external-observation-run:test-1") -> dict[str, object]:
    return {
        "schema": "external-resource-observation-run/v1",
        "run_id": run_id,
        "trace_id": "external-observation:trace-1",
        "activation": "forbidden",
        "provider_business_invocation": False,
        "health_probe_invocation": True,
        "started_at": "2026-08-03T00:00:00Z",
        "finished_at": "2026-08-03T00:00:00Z",
        "catalog_observation_id": "external-resource-observation:catalog-1",
        "catalog_digest": "sha256:catalog-1",
        "result_state": "degraded",
        "summary": {
            "resource_count": 2,
            "healthy_count": 1,
            "degraded_count": 0,
            "unavailable_count": 1,
            "error_count": 0,
            "probe_count": 2,
            "probe_failure_count": 1,
        },
        "latency": {
            "duration_ms": 12.5,
            "probe_latency_ms_sum": 8,
            "probe_latency_ms_max": 8,
        },
        "cost": {
            "state": "unmetered",
            "amount": None,
            "currency": "USD",
            "basis": "read-only health probe",
        },
        "actor": "test",
        "source_ref": "test:observation-run",
    }


def test_run_receipt_is_durable_idempotent_and_credential_free(tmp_path):
    first = record_external_observation_run(tmp_path, _payload())
    second = record_external_observation_run(tmp_path, _payload())

    assert first["status"] == "recorded"
    assert second["status"] == "deduplicated"
    receipt = first["receipt"]
    assert receipt["schema"] == "external-resource-observation-run/v1"
    assert receipt["result_state"] == "degraded"
    assert receipt["cost"]["state"] == "unmetered"
    assert len(read_external_observation_runs(tmp_path)) == 1


def test_run_receipt_rejects_business_invocation_and_raw_payload(tmp_path):
    payload = _payload()
    payload["provider_business_invocation"] = True
    with pytest.raises(ExternalObservationRunError, match="business invocation"):
        record_external_observation_run(tmp_path, payload)

    payload = _payload()
    payload["summary"] = {"output": "private"}
    with pytest.raises(ExternalObservationRunError, match="forbidden"):
        record_external_observation_run(tmp_path, payload)


def test_conflicting_run_id_fails_closed(tmp_path):
    record_external_observation_run(tmp_path, _payload())
    changed = _payload()
    changed["result_state"] = "succeeded"
    with pytest.raises(ExternalObservationRunError, match="conflicting"):
        record_external_observation_run(tmp_path, changed)
