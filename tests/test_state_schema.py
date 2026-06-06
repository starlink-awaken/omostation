from __future__ import annotations

import pytest

from runtime.state_schema import validate_runtime_health_snapshot


def test_validate_runtime_health_snapshot_accepts_runtime_shape():
    payload = {
        "last_scan": 1.0,
        "services": {
            "agora": {
                "name": "agora",
                "type": "daemon",
                "runtime": {"status": "running"},
            }
        },
    }

    assert validate_runtime_health_snapshot(payload) == payload


def test_validate_runtime_health_snapshot_rejects_governance_keys():
    with pytest.raises(ValueError, match="governance-only keys"):
        validate_runtime_health_snapshot(
            {
                "last_scan": 1.0,
                "services": {},
                "current_phase": 28,
            }
        )


def test_validate_runtime_health_snapshot_requires_services_mapping():
    with pytest.raises(ValueError, match="services must be a mapping"):
        validate_runtime_health_snapshot({"last_scan": 1.0, "services": []})
