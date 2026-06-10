from __future__ import annotations

import pytest

from omo.omo_debt_reporting_history import build_reporting_history_packet, render_reporting_history_markdown


def _dispatch_runs() -> tuple[dict[str, str], ...]:
    return (
        {
            "run_stamp": "2026-06-10T00-00-00Z",
            "dispatch_run_ref": ".omo/debt/dispatch/runs/2026-06-10T00-00-00Z.yaml",
        },
        {
            "run_stamp": "2026-06-01T00-00-00Z",
            "dispatch_run_ref": ".omo/debt/dispatch/runs/2026-06-01T00-00-00Z.yaml",
        },
    )


def _reporting_packet(
    run_stamp: str,
    *,
    generated_at: str,
    total_items: int,
    executed_item_count: int,
    approval_coverage_rate: float,
    execution_completion_rate: float,
) -> dict[str, object]:
    return {
        "generated_at": generated_at,
        "dispatch_run_ref": f".omo/debt/dispatch/runs/{run_stamp}.yaml",
        "run_stamp": run_stamp,
        "summary": {
            "owner_count": 2,
            "total_items": total_items,
            "state_counts": {
                "pending_approval": 1,
                "ready_to_execute": total_items - executed_item_count - 1,
                "executed": executed_item_count,
            },
            "gate_item_count": 1,
            "approved_gate_item_count": 1 if approval_coverage_rate == 1.0 else 0,
            "approval_coverage_rate": approval_coverage_rate,
            "executed_item_count": executed_item_count,
            "execution_completion_rate": execution_completion_rate,
        },
        "owners": [],
    }


def test_build_reporting_history_packet_orders_runs_and_sets_latest_prior() -> None:
    packet = build_reporting_history_packet(
        generated_at="2026-06-12T00:00:00Z",
        dispatch_runs=tuple(reversed(_dispatch_runs())),
        reporting_packets_by_run={
            "2026-06-10T00-00-00Z": _reporting_packet(
                "2026-06-10T00-00-00Z",
                generated_at="2026-06-12T00:00:00Z",
                total_items=9,
                executed_item_count=2,
                approval_coverage_rate=1.0,
                execution_completion_rate=2 / 9,
            ),
            "2026-06-01T00-00-00Z": _reporting_packet(
                "2026-06-01T00-00-00Z",
                generated_at="2026-06-01T02:00:00Z",
                total_items=9,
                executed_item_count=0,
                approval_coverage_rate=0.0,
                execution_completion_rate=0.0,
            ),
        },
    )

    assert packet["latest_run_stamp"] == "2026-06-10T00-00-00Z"
    assert packet["prior_run_stamp"] == "2026-06-01T00-00-00Z"
    assert packet["run_count"] == 2
    assert [entry["run_stamp"] for entry in packet["runs"]] == [
        "2026-06-10T00-00-00Z",
        "2026-06-01T00-00-00Z",
    ]
    assert packet["runs"][0]["reporting_exists"] is True
    assert packet["runs"][0]["approval_coverage_rate"] == 1.0


def test_build_reporting_history_packet_marks_missing_reporting_artifacts_without_dropping_run() -> None:
    packet = build_reporting_history_packet(
        generated_at="2026-06-12T00:00:00Z",
        dispatch_runs=_dispatch_runs(),
        reporting_packets_by_run={
            "2026-06-10T00-00-00Z": _reporting_packet(
                "2026-06-10T00-00-00Z",
                generated_at="2026-06-12T00:00:00Z",
                total_items=9,
                executed_item_count=1,
                approval_coverage_rate=1.0,
                execution_completion_rate=1 / 9,
            )
        },
    )

    assert packet["run_count"] == 2
    assert packet["prior_run_stamp"] == "2026-06-01T00-00-00Z"
    assert packet["runs"][1] == {
        "run_stamp": "2026-06-01T00-00-00Z",
        "dispatch_run_ref": ".omo/debt/dispatch/runs/2026-06-01T00-00-00Z.yaml",
        "reporting_ref": None,
        "reporting_exists": False,
        "report_generated_at": None,
        "total_items": None,
        "executed_item_count": None,
        "approval_coverage_rate": None,
        "execution_completion_rate": None,
    }


def test_build_reporting_history_packet_rejects_duplicate_or_malformed_run_stamps() -> None:
    with pytest.raises(ValueError, match="duplicate dispatch run stamp"):
        build_reporting_history_packet(
            generated_at="2026-06-12T00:00:00Z",
            dispatch_runs=(
                {
                    "run_stamp": "2026-06-10T00-00-00Z",
                    "dispatch_run_ref": ".omo/debt/dispatch/runs/2026-06-10T00-00-00Z.yaml",
                },
                {
                    "run_stamp": "2026-06-10T00-00-00Z",
                    "dispatch_run_ref": ".omo/debt/dispatch/runs/2026-06-10T00-00-00Z-copy.yaml",
                },
            ),
            reporting_packets_by_run={},
        )

    with pytest.raises(ValueError, match="invalid dispatch run stamp"):
        build_reporting_history_packet(
            generated_at="2026-06-12T00:00:00Z",
            dispatch_runs=(
                {
                    "run_stamp": "not-a-run-stamp",
                    "dispatch_run_ref": ".omo/debt/dispatch/runs/not-a-run-stamp.yaml",
                },
            ),
            reporting_packets_by_run={},
        )


def test_render_reporting_history_markdown_lists_latest_prior_and_run_presence() -> None:
    packet = build_reporting_history_packet(
        generated_at="2026-06-12T00:00:00Z",
        dispatch_runs=_dispatch_runs(),
        reporting_packets_by_run={
            "2026-06-10T00-00-00Z": _reporting_packet(
                "2026-06-10T00-00-00Z",
                generated_at="2026-06-12T00:00:00Z",
                total_items=9,
                executed_item_count=2,
                approval_coverage_rate=1.0,
                execution_completion_rate=2 / 9,
            )
        },
    )

    markdown = render_reporting_history_markdown(packet)

    assert "# Debt Reporting History" in markdown
    assert "Latest run: 2026-06-10T00-00-00Z" in markdown
    assert "Prior run: 2026-06-01T00-00-00Z" in markdown
    assert "reporting_exists=yes" in markdown
    assert "reporting_exists=no" in markdown
