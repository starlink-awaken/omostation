from __future__ import annotations

from pathlib import Path

import pytest

from omo.omo_debt_approval import (
    APPROVAL_SCOPE_EXECUTE_REVALIDATE,
    approval_current_path,
    approval_paths,
    build_approval_record,
    dispatch_entry_requires_approval,
    find_dispatch_entry,
)


def _dispatch_packet() -> dict[str, object]:
    return {
        "latest_run_ref": ".omo/debt/dispatch/runs/2026-06-10T00-00-00Z.yaml",
        "owners": [
            {
                "owner": "sharedbrain-governance",
                "entries": [
                    {
                        "id": "SB_DECOMPOSITION",
                        "primary_lane": "revalidate_now",
                        "gate_level": "gate",
                    },
                    {
                        "id": "SB_UNTESTED_PKGS",
                        "primary_lane": "revalidate_now",
                        "gate_level": "watchlist",
                    },
                ],
            },
            {
                "owner": "platform-governance",
                "entries": [
                    {
                        "id": "D2_CI_E2E",
                        "primary_lane": "revalidate_now",
                        "gate_level": "watchlist",
                    }
                ],
            },
        ],
    }


def test_dispatch_entry_requires_approval_only_for_gate_revalidate_items() -> None:
    packet = _dispatch_packet()

    assert dispatch_entry_requires_approval(find_dispatch_entry(packet, "SB_DECOMPOSITION")) is True
    assert dispatch_entry_requires_approval(find_dispatch_entry(packet, "SB_UNTESTED_PKGS")) is False
    assert dispatch_entry_requires_approval(find_dispatch_entry(packet, "D2_CI_E2E")) is False
    assert dispatch_entry_requires_approval(find_dispatch_entry(packet, "MISSING")) is False


def test_build_approval_record_and_paths_use_immutable_run_ref() -> None:
    current_only_path = approval_current_path(Path("/tmp/example/.omo"), item_id="SB_DECOMPOSITION")
    current_path, record_path = approval_paths(
        Path("/tmp/example/.omo"),
        item_id="SB_DECOMPOSITION",
        approved_at="2026-06-10T01:00:00Z",
    )

    record = build_approval_record(
        item_id="SB_DECOMPOSITION",
        approved_by="omo-governance",
        approved_at="2026-06-10T01:00:00Z",
        dispatch_run_ref=".omo/debt/dispatch/runs/2026-06-10T00-00-00Z.yaml",
        approval_scope=APPROVAL_SCOPE_EXECUTE_REVALIDATE,
    )

    assert current_only_path == Path("/tmp/example/.omo/debt/approvals/SB_DECOMPOSITION/current.yaml")
    assert current_path == current_only_path
    assert record_path == Path("/tmp/example/.omo/debt/approvals/SB_DECOMPOSITION/records/2026-06-10T01-00-00Z.yaml")
    assert record == {
        "item_id": "SB_DECOMPOSITION",
        "approved_by": "omo-governance",
        "approved_at": "2026-06-10T01:00:00Z",
        "dispatch_run_ref": ".omo/debt/dispatch/runs/2026-06-10T00-00-00Z.yaml",
        "approval_scope": "execute_revalidate",
    }


def test_build_approval_record_rejects_invalid_scope() -> None:
    with pytest.raises(ValueError, match="invalid approval scope"):
        build_approval_record(
            item_id="SB_DECOMPOSITION",
            approved_by="omo-governance",
            approved_at="2026-06-10T01:00:00Z",
            dispatch_run_ref=".omo/debt/dispatch/runs/2026-06-10T00-00-00Z.yaml",
            approval_scope="watch_only",
        )
