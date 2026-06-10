from __future__ import annotations

import pytest

from omo.omo_state_schema import (
    summarize_system_health_snapshot,
    validate_system_health_snapshot,
    validate_system_state,
)


def test_validate_system_health_snapshot_rejects_governance_keys():
    with pytest.raises(ValueError, match="governance-only keys"):
        validate_system_health_snapshot(
            {
                "last_scan": 1,
                "services": {},
                "current_phase": 28,
            }
        )


def test_validate_system_state_rejects_runtime_snapshot_keys():
    with pytest.raises(ValueError, match="runtime-snapshot keys"):
        validate_system_state(
            {
                "current_phase": 28,
                "services": {},
            }
        )


def test_summarize_system_health_snapshot_returns_runtime_summary_only():
    summary = summarize_system_health_snapshot(
        {
            "last_scan": 123.0,
            "services": {
                "agora": {
                    "port_listening": True,
                    "health_check": "healthy",
                    "runtime": {"freshness_seconds": 5},
                },
                "gbrain": {
                    "port_listening": False,
                    "health_check": "unreachable",
                    "runtime": {"freshness_seconds": 90000},
                },
            },
        }
    )

    assert summary == {
        "last_scan": 123.0,
        "total_services": 2,
        "online_services": 1,
        "healthy_services": 1,
        "offline_services": 1,
        "unhealthy_services": ["gbrain"],
        "stale_services": ["gbrain"],
    }
