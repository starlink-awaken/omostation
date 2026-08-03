from __future__ import annotations

import pytest
from omo.omo_external_scene_consumer import (
    ExternalSceneConsumerError,
    read_external_scene_consumers,
    record_external_scene_consumer,
)


def _payload(consumer_id: str = "consumer:test") -> dict[str, object]:
    return {
        "schema": "external-scene-consumer/v1",
        "consumer_id": consumer_id,
        "consumer_ref": "ref://consumer/test",
        "consumer_kind": "workflow",
        "scene_binding": {
            "scene_id": "scene:test",
            "journey_id": "journey:test",
            "outcome_metric": "metric:test",
        },
        "owner_ref": "ref://owner/test",
        "entrypoint_ref": "ref://entrypoint/test",
        "capability_ref": "ref://capability/test",
        "permission_ref": "ref://permission/test",
        "metric_ref": "ref://metric/test",
        "rollback_ref": "ref://rollback/test",
        "evidence_refs": ["evidence://consumer/test"],
        "status": "declared",
        "activation": "forbidden",
        "provider_invocation": False,
        "workflow_run_id": None,
        "actor": "test",
        "source_ref": "test:scene-consumer",
        "observed_at": "2026-08-03T00:00:00Z",
    }


def test_consumer_contract_is_durable_and_idempotent(tmp_path):
    first = record_external_scene_consumer(tmp_path, _payload())
    second = record_external_scene_consumer(tmp_path, _payload())

    assert first["status"] == "recorded"
    assert second["status"] == "deduplicated"
    assert first["receipt"]["schema"] == "external-scene-consumer/v1"
    assert first["receipt"]["activation"] == "forbidden"
    assert first["receipt"]["workflow_run_id"] is None
    assert len(read_external_scene_consumers(tmp_path)) == 1


def test_consumer_contract_rejects_activation_run_and_raw_content(tmp_path):
    payload = _payload()
    payload["activation"] = "allowed"
    with pytest.raises(ExternalSceneConsumerError, match="activation"):
        record_external_scene_consumer(tmp_path, payload)

    payload = _payload()
    payload["workflow_run_id"] = "run-should-not-exist"
    with pytest.raises(ExternalSceneConsumerError, match="WorkflowRun"):
        record_external_scene_consumer(tmp_path, payload)

    payload = _payload()
    payload["output"] = "private"
    with pytest.raises(ExternalSceneConsumerError, match="forbidden"):
        record_external_scene_consumer(tmp_path, payload)


def test_consumer_contract_requires_valid_kind_and_opaque_refs(tmp_path):
    payload = _payload()
    payload["consumer_kind"] = "unknown"
    with pytest.raises(ExternalSceneConsumerError, match="consumer kind"):
        record_external_scene_consumer(tmp_path, payload)

    payload = _payload()
    payload["entrypoint_ref"] = "https://example.invalid/run"
    with pytest.raises(ExternalSceneConsumerError, match="opaque"):
        record_external_scene_consumer(tmp_path, payload)
