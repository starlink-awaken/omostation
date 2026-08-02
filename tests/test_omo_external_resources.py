from __future__ import annotations

import json
from pathlib import Path

import pytest
from omo.omo_external_resources import (
    ExternalResourceObservationError,
    read_latest_external_resource_observation,
    record_external_resource_observation,
)


def _catalog(*, observed_at: str = "2026-08-02T00:00:00Z", changes=None) -> dict:
    payload = {
        "schema": "external-resource-catalog/v1",
        "mode": "read_only_projection",
        "activation": "forbidden",
        "raw_content_policy": "never_read_or_export",
        "observed_at": observed_at,
        "health_ttl_seconds": 900,
        "policy_digest": "external-connection-fabric/v1",
        "resources": [
            {
                "id": "source:test",
                "kind": "knowledge_source",
                "provider": "test-provider",
                "availability": "available",
                "reason_codes": [],
                "health": {"status": "healthy", "source": "probe:test"},
            }
        ],
        "errors": [],
        "summary": {
            "resource_count": 1,
            "unavailable_count": 0,
            "error_count": 0,
        },
    }
    if changes is not None:
        payload["changes"] = changes
    return payload


def _diff(change_count: int = 1, *, review_required: bool = False) -> dict:
    return {
        "schema": "external-resource-catalog-diff/v1",
        "changes": [],
        "error_changes": [],
        "summary": {
            "change_count": change_count,
            "error_change_count": 0,
            "review_required": review_required,
            "review_required_count": change_count if review_required else 0,
            "operational_observation_count": 0 if review_required else change_count,
            "risk_codes": ["descriptor_provider_changed"] if review_required else ["health_changed"],
        },
    }


def test_records_safe_observation_and_latest_projection(tmp_path: Path) -> None:
    result = record_external_resource_observation(tmp_path, _catalog())

    assert result["status"] == "recorded"
    observation = result["observation"]
    assert observation["schema"] == "external-resource-observation/v1"
    assert observation["change_state"] == "baseline"
    assert read_latest_external_resource_observation(tmp_path) == observation
    lines = (tmp_path / "_log/external-resource-observations.jsonl").read_text()
    assert len(lines.splitlines()) == 1
    assert "password" not in lines


def test_same_observation_is_idempotently_deduplicated(tmp_path: Path) -> None:
    first = record_external_resource_observation(tmp_path, _catalog())
    second = record_external_resource_observation(tmp_path, _catalog())

    assert first["status"] == "recorded"
    assert second["status"] == "deduplicated"
    lines = (tmp_path / "_log/external-resource-observations.jsonl").read_text()
    assert len(lines.splitlines()) == 1


def test_changed_observation_keeps_change_summary(tmp_path: Path) -> None:
    record_external_resource_observation(tmp_path, _catalog())
    changed = _catalog(
        observed_at="2026-08-02T00:05:00Z",
        changes=_diff(),
    )

    result = record_external_resource_observation(tmp_path, changed)

    assert result["observation"]["change_state"] == "changed"
    assert result["observation"]["change_summary"]["change_count"] == 1
    assert len(result["observation"]["catalog"]["changes"]["changes"]) == 0


def test_observation_rejects_raw_content_and_wrong_activation(tmp_path: Path) -> None:
    payload = _catalog()
    payload["resources"][0]["raw_content"] = "private body"
    with pytest.raises(ExternalResourceObservationError, match="forbidden"):
        record_external_resource_observation(tmp_path, payload)

    payload = _catalog()
    payload["activation"] = "allowed"
    with pytest.raises(ExternalResourceObservationError, match="activation"):
        record_external_resource_observation(tmp_path, payload)


def test_latest_falls_back_to_append_only_log(tmp_path: Path) -> None:
    result = record_external_resource_observation(tmp_path, _catalog())
    latest_path = tmp_path / "_log/external-resource-observation-latest.json"
    latest_path.unlink()

    latest = read_latest_external_resource_observation(tmp_path)

    assert latest == result["observation"]
    json.loads(
        (tmp_path / "_log/external-resource-observations.jsonl")
        .read_text()
        .splitlines()[0]
    )


def test_observation_projects_manual_review_requirement(tmp_path: Path) -> None:
    result = record_external_resource_observation(
        tmp_path,
        _catalog(
            observed_at="2026-08-02T00:05:00Z",
            changes=_diff(review_required=True),
        ),
    )

    assert result["observation"]["change_summary"] == {
        "change_count": 1,
        "error_change_count": 0,
        "review_required": True,
        "review_required_count": 1,
        "operational_observation_count": 0,
        "risk_codes": ["descriptor_provider_changed"],
    }
