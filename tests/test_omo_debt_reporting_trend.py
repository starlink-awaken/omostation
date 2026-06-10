from __future__ import annotations

import pytest

from omo.omo_debt_reporting_trend import build_reporting_trend_packet, render_reporting_trend_markdown


def _history_entry(
    run_stamp: str,
    *,
    total_items: int,
    executed_item_count: int,
    approval_coverage_rate: float,
    execution_completion_rate: float,
) -> dict[str, object]:
    return {
        "run_stamp": run_stamp,
        "dispatch_run_ref": f".omo/debt/dispatch/runs/{run_stamp}.yaml",
        "reporting_ref": f".omo/debt/reporting/runs/{run_stamp}/current.yaml",
        "reporting_exists": True,
        "report_generated_at": "2026-06-12T00:00:00Z",
        "total_items": total_items,
        "executed_item_count": executed_item_count,
        "approval_coverage_rate": approval_coverage_rate,
        "execution_completion_rate": execution_completion_rate,
    }


def _owner_entry(
    owner: str,
    *,
    item_count: int,
    executed_item_count: int,
    approval_coverage_rate: float,
    execution_completion_rate: float,
) -> dict[str, object]:
    return {
        "owner": owner,
        "item_count": item_count,
        "state_counts": {
            "pending_approval": 0,
            "ready_to_execute": item_count - executed_item_count,
            "executed": executed_item_count,
        },
        "gate_item_count": item_count,
        "approved_gate_item_count": int(item_count * approval_coverage_rate),
        "approval_coverage_rate": approval_coverage_rate,
        "executed_item_count": executed_item_count,
        "execution_completion_rate": execution_completion_rate,
    }


def _owner_reporting_packet(
    run_stamp: str,
    *,
    owners: list[dict[str, object]],
) -> dict[str, object]:
    return {
        "generated_at": "2026-06-12T00:00:00Z",
        "dispatch_run_ref": f".omo/debt/dispatch/runs/{run_stamp}.yaml",
        "run_stamp": run_stamp,
        "summary": {
            "owner_count": len(owners),
            "total_items": 9,
            "state_counts": {
                "pending_approval": 0,
                "ready_to_execute": 9,
                "executed": 0,
            },
            "gate_item_count": 1,
            "approved_gate_item_count": 0,
            "approval_coverage_rate": 0.0,
            "executed_item_count": 0,
            "execution_completion_rate": 0.0,
        },
        "owners": owners,
    }


def test_build_reporting_trend_packet_reorders_runs_oldest_to_newest() -> None:
    history_packet = {
        "generated_at": "2026-06-12T00:00:00Z",
        "latest_run_stamp": "2026-06-10T00-00-00Z",
        "prior_run_stamp": "2026-06-01T00-00-00Z",
        "run_count": 3,
        "runs": [
            _history_entry(
                "2026-06-10T00-00-00Z",
                total_items=9,
                executed_item_count=0,
                approval_coverage_rate=0.0,
                execution_completion_rate=0.0,
            ),
            _history_entry(
                "2026-06-01T00-00-00Z",
                total_items=9,
                executed_item_count=1,
                approval_coverage_rate=1.0,
                execution_completion_rate=1 / 9,
            ),
            _history_entry(
                "2026-05-20T00-00-00Z",
                total_items=10,
                executed_item_count=0,
                approval_coverage_rate=0.0,
                execution_completion_rate=0.0,
            ),
        ],
    }

    packet = build_reporting_trend_packet(
        generated_at="2026-06-12T01:00:00Z",
        history_packet=history_packet,
    )

    assert packet["trend_status"] == "trend_available"
    assert packet["window_run_count"] == 3
    assert packet["oldest_run_stamp"] == "2026-05-20T00-00-00Z"
    assert packet["latest_run_stamp"] == "2026-06-10T00-00-00Z"
    assert [entry["run_stamp"] for entry in packet["runs"]] == [
        "2026-05-20T00-00-00Z",
        "2026-06-01T00-00-00Z",
        "2026-06-10T00-00-00Z",
    ]
    assert packet["intervals"] == [
        {
            "from_run_stamp": "2026-05-20T00-00-00Z",
            "to_run_stamp": "2026-06-01T00-00-00Z",
            "total_items_delta": -1,
            "executed_item_count_delta": 1,
            "approval_coverage_rate_delta": 1.0,
            "execution_completion_rate_delta": 1 / 9,
        },
        {
            "from_run_stamp": "2026-06-01T00-00-00Z",
            "to_run_stamp": "2026-06-10T00-00-00Z",
            "total_items_delta": 0,
            "executed_item_count_delta": -1,
            "approval_coverage_rate_delta": -1.0,
            "execution_completion_rate_delta": -(1 / 9),
        },
    ]


def test_build_reporting_trend_packet_adds_execution_progress_from_oldest_selected_run() -> None:
    history_packet = {
        "generated_at": "2026-06-12T00:00:00Z",
        "latest_run_stamp": "2026-06-10T00-00-00Z",
        "prior_run_stamp": "2026-06-01T00-00-00Z",
        "run_count": 3,
        "runs": [
            _history_entry(
                "2026-06-10T00-00-00Z",
                total_items=8,
                executed_item_count=3,
                approval_coverage_rate=1.0,
                execution_completion_rate=3 / 8,
            ),
            _history_entry(
                "2026-06-01T00-00-00Z",
                total_items=9,
                executed_item_count=1,
                approval_coverage_rate=1.0,
                execution_completion_rate=1 / 9,
            ),
            _history_entry(
                "2026-05-20T00-00-00Z",
                total_items=10,
                executed_item_count=0,
                approval_coverage_rate=0.0,
                execution_completion_rate=0.0,
            ),
        ],
    }

    packet = build_reporting_trend_packet(
        generated_at="2026-06-12T01:00:00Z",
        history_packet=history_packet,
    )

    assert packet["execution_progress"] == {
        "progress_status": "progress_available",
        "anchor_run_stamp": "2026-05-20T00-00-00Z",
        "baseline_open_item_count": 10,
        "runs": [
            {
                "run_stamp": "2026-05-20T00-00-00Z",
                "open_item_count": 10,
                "open_item_delta_vs_baseline": 0,
                "open_item_ratio_vs_baseline": 1.0,
            },
            {
                "run_stamp": "2026-06-01T00-00-00Z",
                "open_item_count": 8,
                "open_item_delta_vs_baseline": -2,
                "open_item_ratio_vs_baseline": 0.8,
            },
            {
                "run_stamp": "2026-06-10T00-00-00Z",
                "open_item_count": 5,
                "open_item_delta_vs_baseline": -5,
                "open_item_ratio_vs_baseline": 0.5,
            },
        ],
    }


def test_build_reporting_trend_packet_marks_execution_progress_baseline_fully_executed() -> None:
    history_packet = {
        "generated_at": "2026-06-12T00:00:00Z",
        "latest_run_stamp": "2026-06-10T00-00-00Z",
        "prior_run_stamp": "2026-06-01T00-00-00Z",
        "run_count": 2,
        "runs": [
            _history_entry(
                "2026-06-10T00-00-00Z",
                total_items=4,
                executed_item_count=2,
                approval_coverage_rate=1.0,
                execution_completion_rate=0.5,
            ),
            _history_entry(
                "2026-06-01T00-00-00Z",
                total_items=3,
                executed_item_count=3,
                approval_coverage_rate=1.0,
                execution_completion_rate=1.0,
            ),
        ],
    }

    packet = build_reporting_trend_packet(
        generated_at="2026-06-12T01:00:00Z",
        history_packet=history_packet,
    )

    assert packet["execution_progress"] == {
        "progress_status": "baseline_fully_executed",
        "anchor_run_stamp": "2026-06-01T00-00-00Z",
        "baseline_open_item_count": 0,
        "runs": [
            {
                "run_stamp": "2026-06-01T00-00-00Z",
                "open_item_count": 0,
                "open_item_delta_vs_baseline": 0,
                "open_item_ratio_vs_baseline": None,
            },
            {
                "run_stamp": "2026-06-10T00-00-00Z",
                "open_item_count": 2,
                "open_item_delta_vs_baseline": 2,
                "open_item_ratio_vs_baseline": None,
            },
        ],
    }


def test_build_reporting_trend_packet_keeps_execution_progress_unchanged_at_baseline() -> None:
    history_packet = {
        "generated_at": "2026-06-12T00:00:00Z",
        "latest_run_stamp": "2026-06-10T00-00-00Z",
        "prior_run_stamp": "2026-06-01T00-00-00Z",
        "run_count": 2,
        "runs": [
            _history_entry(
                "2026-06-10T00-00-00Z",
                total_items=8,
                executed_item_count=2,
                approval_coverage_rate=1.0,
                execution_completion_rate=0.25,
            ),
            _history_entry(
                "2026-06-01T00-00-00Z",
                total_items=7,
                executed_item_count=1,
                approval_coverage_rate=1.0,
                execution_completion_rate=1 / 7,
            ),
        ],
    }

    packet = build_reporting_trend_packet(
        generated_at="2026-06-12T01:00:00Z",
        history_packet=history_packet,
    )

    assert packet["execution_progress"]["runs"][-1] == {
        "run_stamp": "2026-06-10T00-00-00Z",
        "open_item_count": 6,
        "open_item_delta_vs_baseline": 0,
        "open_item_ratio_vs_baseline": 1.0,
    }


def test_build_reporting_trend_packet_surfaces_execution_progress_increase_vs_baseline() -> None:
    history_packet = {
        "generated_at": "2026-06-12T00:00:00Z",
        "latest_run_stamp": "2026-06-10T00-00-00Z",
        "prior_run_stamp": "2026-06-01T00-00-00Z",
        "run_count": 2,
        "runs": [
            _history_entry(
                "2026-06-10T00-00-00Z",
                total_items=10,
                executed_item_count=1,
                approval_coverage_rate=1.0,
                execution_completion_rate=0.1,
            ),
            _history_entry(
                "2026-06-01T00-00-00Z",
                total_items=8,
                executed_item_count=1,
                approval_coverage_rate=1.0,
                execution_completion_rate=0.125,
            ),
        ],
    }

    packet = build_reporting_trend_packet(
        generated_at="2026-06-12T01:00:00Z",
        history_packet=history_packet,
    )

    assert packet["execution_progress"]["runs"][-1] == {
        "run_stamp": "2026-06-10T00-00-00Z",
        "open_item_count": 9,
        "open_item_delta_vs_baseline": 2,
        "open_item_ratio_vs_baseline": 9 / 7,
    }


def test_build_reporting_trend_packet_leaves_execution_progress_null_when_history_is_insufficient() -> None:
    history_packet = {
        "generated_at": "2026-06-12T00:00:00Z",
        "latest_run_stamp": "2026-06-10T00-00-00Z",
        "prior_run_stamp": None,
        "run_count": 1,
        "runs": [
            _history_entry(
                "2026-06-10T00-00-00Z",
                total_items=9,
                executed_item_count=1,
                approval_coverage_rate=1.0,
                execution_completion_rate=1 / 9,
            )
        ],
    }

    packet = build_reporting_trend_packet(
        generated_at="2026-06-12T01:00:00Z",
        history_packet=history_packet,
    )

    assert packet["trend_status"] == "insufficient_history"
    assert packet["execution_progress"] is None


def test_build_reporting_trend_packet_adds_state_progress_from_selected_reporting_artifacts() -> None:
    history_packet = {
        "generated_at": "2026-06-12T00:00:00Z",
        "latest_run_stamp": "2026-06-10T00-00-00Z",
        "prior_run_stamp": "2026-06-01T00-00-00Z",
        "run_count": 3,
        "runs": [
            _history_entry(
                "2026-06-10T00-00-00Z",
                total_items=8,
                executed_item_count=3,
                approval_coverage_rate=1.0,
                execution_completion_rate=3 / 8,
            ),
            _history_entry(
                "2026-06-01T00-00-00Z",
                total_items=9,
                executed_item_count=1,
                approval_coverage_rate=1.0,
                execution_completion_rate=1 / 9,
            ),
            _history_entry(
                "2026-05-20T00-00-00Z",
                total_items=10,
                executed_item_count=0,
                approval_coverage_rate=0.0,
                execution_completion_rate=0.0,
            ),
        ],
    }

    reporting_packets_by_run = {
        "2026-05-20T00-00-00Z": _owner_reporting_packet("2026-05-20T00-00-00Z", owners=[]),
        "2026-06-01T00-00-00Z": _owner_reporting_packet("2026-06-01T00-00-00Z", owners=[]),
        "2026-06-10T00-00-00Z": _owner_reporting_packet("2026-06-10T00-00-00Z", owners=[]),
    }
    reporting_packets_by_run["2026-05-20T00-00-00Z"]["summary"]["state_counts"] = {
        "pending_approval": 4,
        "ready_to_execute": 6,
        "executed": 0,
    }
    reporting_packets_by_run["2026-06-01T00-00-00Z"]["summary"]["state_counts"] = {
        "pending_approval": 2,
        "ready_to_execute": 6,
        "executed": 1,
    }
    reporting_packets_by_run["2026-06-10T00-00-00Z"]["summary"]["state_counts"] = {
        "pending_approval": 1,
        "ready_to_execute": 4,
        "executed": 3,
    }

    packet = build_reporting_trend_packet(
        generated_at="2026-06-12T01:00:00Z",
        history_packet=history_packet,
        reporting_packets_by_run=reporting_packets_by_run,
    )

    assert packet["state_progress"] == {
        "state_progress_status": "state_progress_available",
        "anchor_run_stamp": "2026-05-20T00-00-00Z",
        "baseline_pending_approval": 4,
        "runs": [
            {
                "run_stamp": "2026-05-20T00-00-00Z",
                "pending_approval": 4,
                "ready_to_execute": 6,
                "executed": 0,
                "pending_approval_delta_vs_baseline": 0,
            },
            {
                "run_stamp": "2026-06-01T00-00-00Z",
                "pending_approval": 2,
                "ready_to_execute": 6,
                "executed": 1,
                "pending_approval_delta_vs_baseline": -2,
            },
            {
                "run_stamp": "2026-06-10T00-00-00Z",
                "pending_approval": 1,
                "ready_to_execute": 4,
                "executed": 3,
                "pending_approval_delta_vs_baseline": -3,
            },
        ],
    }


def test_build_reporting_trend_packet_keeps_state_progress_null_for_insufficient_history() -> None:
    packet = build_reporting_trend_packet(
        generated_at="2026-06-12T01:00:00Z",
        history_packet={
            "generated_at": "2026-06-12T00:00:00Z",
            "latest_run_stamp": "2026-06-10T00-00-00Z",
            "prior_run_stamp": None,
            "run_count": 1,
            "runs": [
                _history_entry(
                    "2026-06-10T00-00-00Z",
                    total_items=8,
                    executed_item_count=3,
                    approval_coverage_rate=1.0,
                    execution_completion_rate=3 / 8,
                )
            ],
        },
    )

    assert packet["state_progress"] is None


def test_build_reporting_trend_packet_aligns_state_progress_anchor_with_execution_progress() -> None:
    history_packet = {
        "generated_at": "2026-06-12T00:00:00Z",
        "latest_run_stamp": "2026-06-10T00-00-00Z",
        "prior_run_stamp": "2026-06-01T00-00-00Z",
        "run_count": 2,
        "runs": [
            _history_entry(
                "2026-06-10T00-00-00Z",
                total_items=8,
                executed_item_count=3,
                approval_coverage_rate=1.0,
                execution_completion_rate=3 / 8,
            ),
            _history_entry(
                "2026-06-01T00-00-00Z",
                total_items=9,
                executed_item_count=1,
                approval_coverage_rate=1.0,
                execution_completion_rate=1 / 9,
            ),
        ],
    }
    reporting_packets_by_run = {
        "2026-06-01T00-00-00Z": _owner_reporting_packet("2026-06-01T00-00-00Z", owners=[]),
        "2026-06-10T00-00-00Z": _owner_reporting_packet("2026-06-10T00-00-00Z", owners=[]),
    }
    reporting_packets_by_run["2026-06-01T00-00-00Z"]["summary"]["state_counts"] = {
        "pending_approval": 2,
        "ready_to_execute": 6,
        "executed": 1,
    }
    reporting_packets_by_run["2026-06-10T00-00-00Z"]["summary"]["state_counts"] = {
        "pending_approval": 4,
        "ready_to_execute": 1,
        "executed": 3,
    }

    packet = build_reporting_trend_packet(
        generated_at="2026-06-12T01:00:00Z",
        history_packet=history_packet,
        reporting_packets_by_run=reporting_packets_by_run,
    )

    assert packet["state_progress"]["anchor_run_stamp"] == packet["execution_progress"]["anchor_run_stamp"]
    assert [run["run_stamp"] for run in packet["state_progress"]["runs"]] == [
        run["run_stamp"] for run in packet["execution_progress"]["runs"]
    ]


def test_build_reporting_trend_packet_keeps_state_progress_unchanged_at_baseline() -> None:
    history_packet = {
        "generated_at": "2026-06-12T00:00:00Z",
        "latest_run_stamp": "2026-06-10T00-00-00Z",
        "prior_run_stamp": "2026-06-01T00-00-00Z",
        "run_count": 2,
        "runs": [
            _history_entry(
                "2026-06-10T00-00-00Z",
                total_items=8,
                executed_item_count=3,
                approval_coverage_rate=1.0,
                execution_completion_rate=3 / 8,
            ),
            _history_entry(
                "2026-06-01T00-00-00Z",
                total_items=9,
                executed_item_count=1,
                approval_coverage_rate=1.0,
                execution_completion_rate=1 / 9,
            ),
        ],
    }
    reporting_packets_by_run = {
        "2026-06-01T00-00-00Z": _owner_reporting_packet("2026-06-01T00-00-00Z", owners=[]),
        "2026-06-10T00-00-00Z": _owner_reporting_packet("2026-06-10T00-00-00Z", owners=[]),
    }
    reporting_packets_by_run["2026-06-01T00-00-00Z"]["summary"]["state_counts"] = {
        "pending_approval": 2,
        "ready_to_execute": 6,
        "executed": 1,
    }
    reporting_packets_by_run["2026-06-10T00-00-00Z"]["summary"]["state_counts"] = {
        "pending_approval": 2,
        "ready_to_execute": 3,
        "executed": 3,
    }

    packet = build_reporting_trend_packet(
        generated_at="2026-06-12T01:00:00Z",
        history_packet=history_packet,
        reporting_packets_by_run=reporting_packets_by_run,
    )

    assert packet["state_progress"]["runs"] == [
        {
            "run_stamp": "2026-06-01T00-00-00Z",
            "pending_approval": 2,
            "ready_to_execute": 6,
            "executed": 1,
            "pending_approval_delta_vs_baseline": 0,
        },
        {
            "run_stamp": "2026-06-10T00-00-00Z",
            "pending_approval": 2,
            "ready_to_execute": 3,
            "executed": 3,
            "pending_approval_delta_vs_baseline": 0,
        },
    ]


def test_build_reporting_trend_packet_reports_state_progress_increase_vs_baseline() -> None:
    history_packet = {
        "generated_at": "2026-06-12T00:00:00Z",
        "latest_run_stamp": "2026-06-10T00-00-00Z",
        "prior_run_stamp": "2026-06-01T00-00-00Z",
        "run_count": 2,
        "runs": [
            _history_entry(
                "2026-06-10T00-00-00Z",
                total_items=8,
                executed_item_count=2,
                approval_coverage_rate=1.0,
                execution_completion_rate=0.25,
            ),
            _history_entry(
                "2026-06-01T00-00-00Z",
                total_items=8,
                executed_item_count=1,
                approval_coverage_rate=1.0,
                execution_completion_rate=0.125,
            ),
        ],
    }
    reporting_packets_by_run = {
        "2026-06-01T00-00-00Z": _owner_reporting_packet("2026-06-01T00-00-00Z", owners=[]),
        "2026-06-10T00-00-00Z": _owner_reporting_packet("2026-06-10T00-00-00Z", owners=[]),
    }
    reporting_packets_by_run["2026-06-01T00-00-00Z"]["summary"]["state_counts"] = {
        "pending_approval": 1,
        "ready_to_execute": 6,
        "executed": 1,
    }
    reporting_packets_by_run["2026-06-10T00-00-00Z"]["summary"]["state_counts"] = {
        "pending_approval": 3,
        "ready_to_execute": 3,
        "executed": 2,
    }

    packet = build_reporting_trend_packet(
        generated_at="2026-06-12T01:00:00Z",
        history_packet=history_packet,
        reporting_packets_by_run=reporting_packets_by_run,
    )

    assert packet["state_progress"]["runs"][-1] == {
        "run_stamp": "2026-06-10T00-00-00Z",
        "pending_approval": 3,
        "ready_to_execute": 3,
        "executed": 2,
        "pending_approval_delta_vs_baseline": 2,
    }


def test_build_reporting_trend_packet_fails_closed_when_state_counts_do_not_match_total_items() -> None:
    history_packet = {
        "generated_at": "2026-06-12T00:00:00Z",
        "latest_run_stamp": "2026-06-10T00-00-00Z",
        "prior_run_stamp": "2026-06-01T00-00-00Z",
        "run_count": 2,
        "runs": [
            _history_entry(
                "2026-06-10T00-00-00Z",
                total_items=8,
                executed_item_count=3,
                approval_coverage_rate=1.0,
                execution_completion_rate=3 / 8,
            ),
            _history_entry(
                "2026-06-01T00-00-00Z",
                total_items=9,
                executed_item_count=1,
                approval_coverage_rate=1.0,
                execution_completion_rate=1 / 9,
            ),
        ],
    }
    reporting_packets_by_run = {
        "2026-06-01T00-00-00Z": _owner_reporting_packet("2026-06-01T00-00-00Z", owners=[]),
        "2026-06-10T00-00-00Z": _owner_reporting_packet("2026-06-10T00-00-00Z", owners=[]),
    }
    reporting_packets_by_run["2026-06-01T00-00-00Z"]["summary"]["state_counts"] = {
        "pending_approval": 2,
        "ready_to_execute": 99,
        "executed": 1,
    }
    reporting_packets_by_run["2026-06-10T00-00-00Z"]["summary"]["state_counts"] = {
        "pending_approval": 1,
        "ready_to_execute": 4,
        "executed": 3,
    }

    with pytest.raises(ValueError, match="invalid state progress counts for run: 2026-06-01T00-00-00Z"):
        build_reporting_trend_packet(
            generated_at="2026-06-12T01:00:00Z",
            history_packet=history_packet,
            reporting_packets_by_run=reporting_packets_by_run,
        )


def test_build_reporting_trend_packet_adds_shared_owner_series() -> None:
    history_packet = {
        "generated_at": "2026-06-12T00:00:00Z",
        "latest_run_stamp": "2026-06-10T00-00-00Z",
        "prior_run_stamp": "2026-06-01T00-00-00Z",
        "run_count": 2,
        "runs": [
            _history_entry(
                "2026-06-10T00-00-00Z",
                total_items=9,
                executed_item_count=1,
                approval_coverage_rate=1.0,
                execution_completion_rate=1 / 9,
            ),
            _history_entry(
                "2026-06-01T00-00-00Z",
                total_items=9,
                executed_item_count=0,
                approval_coverage_rate=0.0,
                execution_completion_rate=0.0,
            ),
        ],
    }

    reporting_packets_by_run = {
        "2026-06-10T00-00-00Z": _owner_reporting_packet(
            "2026-06-10T00-00-00Z",
            owners=[
                _owner_entry(
                    "commerce-governance",
                    item_count=2,
                    executed_item_count=0,
                    approval_coverage_rate=1.0,
                    execution_completion_rate=0.0,
                ),
                _owner_entry(
                    "omo-governance",
                    item_count=3,
                    executed_item_count=1,
                    approval_coverage_rate=1.0,
                    execution_completion_rate=1 / 3,
                ),
            ],
        ),
        "2026-06-01T00-00-00Z": _owner_reporting_packet(
            "2026-06-01T00-00-00Z",
            owners=[
                _owner_entry(
                    "omo-governance",
                    item_count=2,
                    executed_item_count=0,
                    approval_coverage_rate=1.0,
                    execution_completion_rate=0.0,
                ),
                _owner_entry(
                    "commerce-governance",
                    item_count=1,
                    executed_item_count=0,
                    approval_coverage_rate=0.0,
                    execution_completion_rate=0.0,
                ),
            ],
        ),
    }
    reporting_packets_by_run["2026-06-10T00-00-00Z"]["summary"]["state_counts"] = {
        "pending_approval": 0,
        "ready_to_execute": 8,
        "executed": 1,
    }
    reporting_packets_by_run["2026-06-01T00-00-00Z"]["summary"]["state_counts"] = {
        "pending_approval": 0,
        "ready_to_execute": 9,
        "executed": 0,
    }

    packet = build_reporting_trend_packet(
        generated_at="2026-06-12T01:00:00Z",
        history_packet=history_packet,
        reporting_packets_by_run=reporting_packets_by_run,
    )

    assert packet["trend_status"] == "trend_available"
    assert packet["owners"]["owners_trend_status"] == "owners_trend_available"
    assert packet["owners"]["shared_owner_count"] == 2
    assert packet["owners"]["owners_excluded_count"] == 0
    assert [entry["owner"] for entry in packet["owners"]["compared"]] == [
        "commerce-governance",
        "omo-governance",
    ]
    assert packet["owners"]["compared"][0]["runs"][0]["item_count"] == 1
    assert packet["owners"]["compared"][0]["runs"][1]["item_count"] == 2
    assert packet["owners"]["compared"][1]["intervals"][0]["executed_item_count_delta"] == 1


def test_build_reporting_trend_packet_computes_shared_owners_relative_to_selected_window() -> None:
    history_packet = {
        "generated_at": "2026-06-12T00:00:00Z",
        "latest_run_stamp": "2026-06-10T00-00-00Z",
        "prior_run_stamp": "2026-06-01T00-00-00Z",
        "run_count": 3,
        "runs": [
            _history_entry(
                "2026-06-10T00-00-00Z",
                total_items=9,
                executed_item_count=1,
                approval_coverage_rate=1.0,
                execution_completion_rate=1 / 9,
            ),
            _history_entry(
                "2026-06-01T00-00-00Z",
                total_items=9,
                executed_item_count=0,
                approval_coverage_rate=0.0,
                execution_completion_rate=0.0,
            ),
            _history_entry(
                "2026-05-20T00-00-00Z",
                total_items=9,
                executed_item_count=0,
                approval_coverage_rate=0.0,
                execution_completion_rate=0.0,
            ),
        ],
    }

    reporting_packets_by_run = {
        "2026-06-10T00-00-00Z": _owner_reporting_packet(
            "2026-06-10T00-00-00Z",
            owners=[
                _owner_entry(
                    "shared-owner",
                    item_count=2,
                    executed_item_count=1,
                    approval_coverage_rate=1.0,
                    execution_completion_rate=0.5,
                )
            ],
        ),
        "2026-06-01T00-00-00Z": _owner_reporting_packet(
            "2026-06-01T00-00-00Z",
            owners=[
                _owner_entry(
                    "shared-owner",
                    item_count=1,
                    executed_item_count=0,
                    approval_coverage_rate=0.0,
                    execution_completion_rate=0.0,
                )
            ],
        ),
        "2026-05-20T00-00-00Z": _owner_reporting_packet(
            "2026-05-20T00-00-00Z",
            owners=[
                _owner_entry(
                    "older-only",
                    item_count=3,
                    executed_item_count=0,
                    approval_coverage_rate=0.0,
                    execution_completion_rate=0.0,
                )
            ],
        ),
    }
    reporting_packets_by_run["2026-06-10T00-00-00Z"]["summary"]["state_counts"] = {
        "pending_approval": 0,
        "ready_to_execute": 8,
        "executed": 1,
    }
    reporting_packets_by_run["2026-06-01T00-00-00Z"]["summary"]["state_counts"] = {
        "pending_approval": 0,
        "ready_to_execute": 9,
        "executed": 0,
    }
    reporting_packets_by_run["2026-05-20T00-00-00Z"]["summary"]["state_counts"] = {
        "pending_approval": 0,
        "ready_to_execute": 9,
        "executed": 0,
    }

    packet = build_reporting_trend_packet(
        generated_at="2026-06-12T01:00:00Z",
        history_packet=history_packet,
        window_requested=2,
        reporting_packets_by_run=reporting_packets_by_run,
    )

    assert [entry["owner"] for entry in packet["owners"]["compared"]] == ["shared-owner"]
    assert packet["owners"]["owners_excluded_count"] == 0


def test_build_reporting_trend_packet_writes_no_shared_owners_state() -> None:
    history_packet = {
        "generated_at": "2026-06-12T00:00:00Z",
        "latest_run_stamp": "2026-06-10T00-00-00Z",
        "prior_run_stamp": "2026-06-01T00-00-00Z",
        "run_count": 2,
        "runs": [
            _history_entry(
                "2026-06-10T00-00-00Z",
                total_items=9,
                executed_item_count=1,
                approval_coverage_rate=1.0,
                execution_completion_rate=1 / 9,
            ),
            _history_entry(
                "2026-06-01T00-00-00Z",
                total_items=9,
                executed_item_count=0,
                approval_coverage_rate=0.0,
                execution_completion_rate=0.0,
            ),
        ],
    }

    reporting_packets_by_run = {
        "2026-06-10T00-00-00Z": _owner_reporting_packet(
            "2026-06-10T00-00-00Z",
            owners=[
                _owner_entry(
                    "new-owner",
                    item_count=2,
                    executed_item_count=1,
                    approval_coverage_rate=1.0,
                    execution_completion_rate=0.5,
                )
            ],
        ),
        "2026-06-01T00-00-00Z": _owner_reporting_packet(
            "2026-06-01T00-00-00Z",
            owners=[
                _owner_entry(
                    "old-owner",
                    item_count=1,
                    executed_item_count=0,
                    approval_coverage_rate=0.0,
                    execution_completion_rate=0.0,
                )
            ],
        ),
    }
    reporting_packets_by_run["2026-06-10T00-00-00Z"]["summary"]["state_counts"] = {
        "pending_approval": 0,
        "ready_to_execute": 8,
        "executed": 1,
    }
    reporting_packets_by_run["2026-06-01T00-00-00Z"]["summary"]["state_counts"] = {
        "pending_approval": 0,
        "ready_to_execute": 9,
        "executed": 0,
    }

    packet = build_reporting_trend_packet(
        generated_at="2026-06-12T01:00:00Z",
        history_packet=history_packet,
        reporting_packets_by_run=reporting_packets_by_run,
    )

    assert packet["trend_status"] == "trend_available"
    assert packet["owners"] == {
        "owners_trend_status": "no_shared_owners",
        "shared_owner_count": 0,
        "owners_excluded_count": 2,
        "compared": [],
    }


def test_build_reporting_trend_packet_surfaces_excluded_owner_presence_at_window_end() -> None:
    history_packet = {
        "generated_at": "2026-06-12T00:00:00Z",
        "latest_run_stamp": "2026-06-10T00-00-00Z",
        "prior_run_stamp": "2026-06-01T00-00-00Z",
        "run_count": 3,
        "runs": [
            _history_entry(
                "2026-06-10T00-00-00Z",
                total_items=9,
                executed_item_count=1,
                approval_coverage_rate=1.0,
                execution_completion_rate=1 / 9,
            ),
            _history_entry(
                "2026-06-01T00-00-00Z",
                total_items=9,
                executed_item_count=0,
                approval_coverage_rate=0.0,
                execution_completion_rate=0.0,
            ),
            _history_entry(
                "2026-05-20T00-00-00Z",
                total_items=10,
                executed_item_count=0,
                approval_coverage_rate=0.0,
                execution_completion_rate=0.0,
            ),
        ],
    }

    reporting_packets_by_run = {
        "2026-06-10T00-00-00Z": _owner_reporting_packet(
            "2026-06-10T00-00-00Z",
            owners=[
                _owner_entry(
                    "shared-owner",
                    item_count=2,
                    executed_item_count=1,
                    approval_coverage_rate=1.0,
                    execution_completion_rate=0.5,
                ),
                _owner_entry(
                    "late-owner",
                    item_count=1,
                    executed_item_count=0,
                    approval_coverage_rate=1.0,
                    execution_completion_rate=0.0,
                ),
            ],
        ),
        "2026-06-01T00-00-00Z": _owner_reporting_packet(
            "2026-06-01T00-00-00Z",
            owners=[
                _owner_entry(
                    "shared-owner",
                    item_count=1,
                    executed_item_count=0,
                    approval_coverage_rate=0.0,
                    execution_completion_rate=0.0,
                )
            ],
        ),
        "2026-05-20T00-00-00Z": _owner_reporting_packet(
            "2026-05-20T00-00-00Z",
            owners=[
                _owner_entry(
                    "shared-owner",
                    item_count=1,
                    executed_item_count=0,
                    approval_coverage_rate=0.0,
                    execution_completion_rate=0.0,
                )
            ],
        ),
    }
    reporting_packets_by_run["2026-06-10T00-00-00Z"]["summary"]["state_counts"] = {
        "pending_approval": 0,
        "ready_to_execute": 8,
        "executed": 1,
    }
    reporting_packets_by_run["2026-06-01T00-00-00Z"]["summary"]["state_counts"] = {
        "pending_approval": 0,
        "ready_to_execute": 9,
        "executed": 0,
    }
    reporting_packets_by_run["2026-05-20T00-00-00Z"]["summary"]["state_counts"] = {
        "pending_approval": 0,
        "ready_to_execute": 10,
        "executed": 0,
    }

    packet = build_reporting_trend_packet(
        generated_at="2026-06-12T01:00:00Z",
        history_packet=history_packet,
        reporting_packets_by_run=reporting_packets_by_run,
    )

    assert packet["owners"]["owners_excluded_count"] == 1
    assert packet["owner_presence"] == {
        "presence_status": "presence_available",
        "window_run_count": 3,
        "entries": [
            {
                "owner": "late-owner",
                "run_count": 1,
                "first_window_run": "2026-06-10T00-00-00Z",
                "last_window_run": "2026-06-10T00-00-00Z",
                "in_first_window_run": False,
                "in_last_window_run": True,
            }
        ],
    }


def test_build_reporting_trend_packet_surfaces_excluded_owner_presence_at_window_start() -> None:
    history_packet = {
        "generated_at": "2026-06-12T00:00:00Z",
        "latest_run_stamp": "2026-06-10T00-00-00Z",
        "prior_run_stamp": "2026-06-01T00-00-00Z",
        "run_count": 3,
        "runs": [
            _history_entry(
                "2026-06-10T00-00-00Z",
                total_items=9,
                executed_item_count=1,
                approval_coverage_rate=1.0,
                execution_completion_rate=1 / 9,
            ),
            _history_entry(
                "2026-06-01T00-00-00Z",
                total_items=9,
                executed_item_count=0,
                approval_coverage_rate=0.0,
                execution_completion_rate=0.0,
            ),
            _history_entry(
                "2026-05-20T00-00-00Z",
                total_items=10,
                executed_item_count=0,
                approval_coverage_rate=0.0,
                execution_completion_rate=0.0,
            ),
        ],
    }

    reporting_packets_by_run = {
        "2026-06-10T00-00-00Z": _owner_reporting_packet(
            "2026-06-10T00-00-00Z",
            owners=[
                _owner_entry(
                    "shared-owner",
                    item_count=2,
                    executed_item_count=1,
                    approval_coverage_rate=1.0,
                    execution_completion_rate=0.5,
                )
            ],
        ),
        "2026-06-01T00-00-00Z": _owner_reporting_packet(
            "2026-06-01T00-00-00Z",
            owners=[
                _owner_entry(
                    "shared-owner",
                    item_count=1,
                    executed_item_count=0,
                    approval_coverage_rate=0.0,
                    execution_completion_rate=0.0,
                )
            ],
        ),
        "2026-05-20T00-00-00Z": _owner_reporting_packet(
            "2026-05-20T00-00-00Z",
            owners=[
                _owner_entry(
                    "shared-owner",
                    item_count=1,
                    executed_item_count=0,
                    approval_coverage_rate=0.0,
                    execution_completion_rate=0.0,
                ),
                _owner_entry(
                    "early-owner",
                    item_count=2,
                    executed_item_count=0,
                    approval_coverage_rate=0.0,
                    execution_completion_rate=0.0,
                ),
            ],
        ),
    }
    reporting_packets_by_run["2026-06-10T00-00-00Z"]["summary"]["state_counts"] = {
        "pending_approval": 0,
        "ready_to_execute": 8,
        "executed": 1,
    }
    reporting_packets_by_run["2026-06-01T00-00-00Z"]["summary"]["state_counts"] = {
        "pending_approval": 0,
        "ready_to_execute": 9,
        "executed": 0,
    }
    reporting_packets_by_run["2026-05-20T00-00-00Z"]["summary"]["state_counts"] = {
        "pending_approval": 0,
        "ready_to_execute": 10,
        "executed": 0,
    }

    packet = build_reporting_trend_packet(
        generated_at="2026-06-12T01:00:00Z",
        history_packet=history_packet,
        reporting_packets_by_run=reporting_packets_by_run,
    )

    assert packet["owner_presence"] == {
        "presence_status": "presence_available",
        "window_run_count": 3,
        "entries": [
            {
                "owner": "early-owner",
                "run_count": 1,
                "first_window_run": "2026-05-20T00-00-00Z",
                "last_window_run": "2026-05-20T00-00-00Z",
                "in_first_window_run": True,
                "in_last_window_run": False,
            }
        ],
    }


def test_build_reporting_trend_packet_surfaces_excluded_owner_presence_in_middle_runs() -> None:
    history_packet = {
        "generated_at": "2026-06-12T00:00:00Z",
        "latest_run_stamp": "2026-06-10T00-00-00Z",
        "prior_run_stamp": "2026-06-01T00-00-00Z",
        "run_count": 3,
        "runs": [
            _history_entry(
                "2026-06-10T00-00-00Z",
                total_items=9,
                executed_item_count=1,
                approval_coverage_rate=1.0,
                execution_completion_rate=1 / 9,
            ),
            _history_entry(
                "2026-06-01T00-00-00Z",
                total_items=9,
                executed_item_count=0,
                approval_coverage_rate=0.0,
                execution_completion_rate=0.0,
            ),
            _history_entry(
                "2026-05-20T00-00-00Z",
                total_items=10,
                executed_item_count=0,
                approval_coverage_rate=0.0,
                execution_completion_rate=0.0,
            ),
        ],
    }

    reporting_packets_by_run = {
        "2026-06-10T00-00-00Z": _owner_reporting_packet(
            "2026-06-10T00-00-00Z",
            owners=[
                _owner_entry(
                    "shared-owner",
                    item_count=2,
                    executed_item_count=1,
                    approval_coverage_rate=1.0,
                    execution_completion_rate=0.5,
                )
            ],
        ),
        "2026-06-01T00-00-00Z": _owner_reporting_packet(
            "2026-06-01T00-00-00Z",
            owners=[
                _owner_entry(
                    "shared-owner",
                    item_count=1,
                    executed_item_count=0,
                    approval_coverage_rate=0.0,
                    execution_completion_rate=0.0,
                ),
                _owner_entry(
                    "middle-owner",
                    item_count=1,
                    executed_item_count=0,
                    approval_coverage_rate=0.0,
                    execution_completion_rate=0.0,
                ),
            ],
        ),
        "2026-05-20T00-00-00Z": _owner_reporting_packet(
            "2026-05-20T00-00-00Z",
            owners=[
                _owner_entry(
                    "shared-owner",
                    item_count=1,
                    executed_item_count=0,
                    approval_coverage_rate=0.0,
                    execution_completion_rate=0.0,
                )
            ],
        ),
    }
    reporting_packets_by_run["2026-06-10T00-00-00Z"]["summary"]["state_counts"] = {
        "pending_approval": 0,
        "ready_to_execute": 8,
        "executed": 1,
    }
    reporting_packets_by_run["2026-06-01T00-00-00Z"]["summary"]["state_counts"] = {
        "pending_approval": 0,
        "ready_to_execute": 9,
        "executed": 0,
    }
    reporting_packets_by_run["2026-05-20T00-00-00Z"]["summary"]["state_counts"] = {
        "pending_approval": 0,
        "ready_to_execute": 10,
        "executed": 0,
    }

    packet = build_reporting_trend_packet(
        generated_at="2026-06-12T01:00:00Z",
        history_packet=history_packet,
        reporting_packets_by_run=reporting_packets_by_run,
    )

    assert packet["owner_presence"] == {
        "presence_status": "presence_available",
        "window_run_count": 3,
        "entries": [
            {
                "owner": "middle-owner",
                "run_count": 1,
                "first_window_run": "2026-06-01T00-00-00Z",
                "last_window_run": "2026-06-01T00-00-00Z",
                "in_first_window_run": False,
                "in_last_window_run": False,
            }
        ],
    }


def test_build_reporting_trend_packet_writes_no_excluded_owner_presence_state() -> None:
    history_packet = {
        "generated_at": "2026-06-12T00:00:00Z",
        "latest_run_stamp": "2026-06-10T00-00-00Z",
        "prior_run_stamp": "2026-06-01T00-00-00Z",
        "run_count": 2,
        "runs": [
            _history_entry(
                "2026-06-10T00-00-00Z",
                total_items=9,
                executed_item_count=1,
                approval_coverage_rate=1.0,
                execution_completion_rate=1 / 9,
            ),
            _history_entry(
                "2026-06-01T00-00-00Z",
                total_items=9,
                executed_item_count=0,
                approval_coverage_rate=0.0,
                execution_completion_rate=0.0,
            ),
        ],
    }

    reporting_packets_by_run = {
        "2026-06-10T00-00-00Z": _owner_reporting_packet(
            "2026-06-10T00-00-00Z",
            owners=[
                _owner_entry(
                    "shared-owner",
                    item_count=2,
                    executed_item_count=1,
                    approval_coverage_rate=1.0,
                    execution_completion_rate=0.5,
                )
            ],
        ),
        "2026-06-01T00-00-00Z": _owner_reporting_packet(
            "2026-06-01T00-00-00Z",
            owners=[
                _owner_entry(
                    "shared-owner",
                    item_count=1,
                    executed_item_count=0,
                    approval_coverage_rate=0.0,
                    execution_completion_rate=0.0,
                )
            ],
        ),
    }
    reporting_packets_by_run["2026-06-10T00-00-00Z"]["summary"]["state_counts"] = {
        "pending_approval": 0,
        "ready_to_execute": 8,
        "executed": 1,
    }
    reporting_packets_by_run["2026-06-01T00-00-00Z"]["summary"]["state_counts"] = {
        "pending_approval": 0,
        "ready_to_execute": 9,
        "executed": 0,
    }

    packet = build_reporting_trend_packet(
        generated_at="2026-06-12T01:00:00Z",
        history_packet=history_packet,
        reporting_packets_by_run=reporting_packets_by_run,
    )

    assert packet["owners"]["owners_excluded_count"] == 0
    assert packet["owner_presence"] == {
        "presence_status": "no_excluded_owners",
        "window_run_count": 2,
        "entries": [],
    }


def test_build_reporting_trend_packet_writes_insufficient_history_state() -> None:
    history_packet = {
        "generated_at": "2026-06-12T00:00:00Z",
        "latest_run_stamp": "2026-06-10T00-00-00Z",
        "prior_run_stamp": None,
        "run_count": 1,
        "runs": [
            _history_entry(
                "2026-06-10T00-00-00Z",
                total_items=9,
                executed_item_count=0,
                approval_coverage_rate=0.0,
                execution_completion_rate=0.0,
            )
        ],
    }

    packet = build_reporting_trend_packet(
        generated_at="2026-06-12T01:00:00Z",
        history_packet=history_packet,
    )

    assert packet["trend_status"] == "insufficient_history"
    assert packet["window_run_count"] == 1
    assert packet["oldest_run_stamp"] == "2026-06-10T00-00-00Z"
    assert packet["latest_run_stamp"] == "2026-06-10T00-00-00Z"
    assert len(packet["runs"]) == 1
    assert packet["intervals"] == []


def test_build_reporting_trend_packet_omits_owner_block_for_insufficient_history() -> None:
    history_packet = {
        "generated_at": "2026-06-12T00:00:00Z",
        "latest_run_stamp": "2026-06-10T00-00-00Z",
        "prior_run_stamp": None,
        "run_count": 1,
        "runs": [
            _history_entry(
                "2026-06-10T00-00-00Z",
                total_items=9,
                executed_item_count=0,
                approval_coverage_rate=0.0,
                execution_completion_rate=0.0,
            )
        ],
    }

    packet = build_reporting_trend_packet(
        generated_at="2026-06-12T01:00:00Z",
        history_packet=history_packet,
        reporting_packets_by_run={
            "2026-06-10T00-00-00Z": _owner_reporting_packet(
                "2026-06-10T00-00-00Z",
                owners=[
                    _owner_entry(
                        "omo-governance",
                        item_count=3,
                        executed_item_count=0,
                        approval_coverage_rate=0.0,
                        execution_completion_rate=0.0,
                    )
                ],
            )
        },
    )

    assert packet["trend_status"] == "insufficient_history"
    assert packet["owners"] is None
    assert packet["owner_presence"] is None


def test_build_reporting_trend_packet_rejects_missing_reporting_metadata() -> None:
    history_packet = {
        "generated_at": "2026-06-12T00:00:00Z",
        "latest_run_stamp": "2026-06-10T00-00-00Z",
        "prior_run_stamp": "2026-06-01T00-00-00Z",
        "run_count": 2,
        "runs": [
            _history_entry(
                "2026-06-10T00-00-00Z",
                total_items=9,
                executed_item_count=0,
                approval_coverage_rate=0.0,
                execution_completion_rate=0.0,
            ),
            {
                "run_stamp": "2026-06-01T00-00-00Z",
                "dispatch_run_ref": ".omo/debt/dispatch/runs/2026-06-01T00-00-00Z.yaml",
                "reporting_ref": None,
                "reporting_exists": False,
                "report_generated_at": None,
                "total_items": None,
                "executed_item_count": None,
                "approval_coverage_rate": None,
                "execution_completion_rate": None,
            },
        ],
    }

    with pytest.raises(ValueError, match="missing reporting trend metadata for run: 2026-06-01T00-00-00Z"):
        build_reporting_trend_packet(
            generated_at="2026-06-12T01:00:00Z",
            history_packet=history_packet,
        )


def test_build_reporting_trend_packet_rejects_missing_owner_reporting_packet() -> None:
    history_packet = {
        "generated_at": "2026-06-12T00:00:00Z",
        "latest_run_stamp": "2026-06-10T00-00-00Z",
        "prior_run_stamp": "2026-06-01T00-00-00Z",
        "run_count": 2,
        "runs": [
            _history_entry(
                "2026-06-10T00-00-00Z",
                total_items=9,
                executed_item_count=1,
                approval_coverage_rate=1.0,
                execution_completion_rate=1 / 9,
            ),
            _history_entry(
                "2026-06-01T00-00-00Z",
                total_items=9,
                executed_item_count=0,
                approval_coverage_rate=0.0,
                execution_completion_rate=0.0,
            ),
        ],
    }

    with pytest.raises(ValueError, match="missing owner reporting packet for run: 2026-06-01T00-00-00Z"):
        build_reporting_trend_packet(
            generated_at="2026-06-12T01:00:00Z",
            history_packet=history_packet,
            reporting_packets_by_run={
                "2026-06-10T00-00-00Z": _owner_reporting_packet(
                    "2026-06-10T00-00-00Z",
                    owners=[
                        _owner_entry(
                            "omo-governance",
                            item_count=3,
                            executed_item_count=1,
                            approval_coverage_rate=1.0,
                            execution_completion_rate=1 / 3,
                        )
                    ],
                )
            },
        )


def test_build_reporting_trend_packet_selects_most_recent_window_before_reordering() -> None:
    history_packet = {
        "generated_at": "2026-06-12T00:00:00Z",
        "latest_run_stamp": "2026-06-10T00-00-00Z",
        "prior_run_stamp": "2026-06-01T00-00-00Z",
        "run_count": 5,
        "runs": [
            _history_entry(
                "2026-06-10T00-00-00Z",
                total_items=9,
                executed_item_count=0,
                approval_coverage_rate=0.0,
                execution_completion_rate=0.0,
            ),
            _history_entry(
                "2026-06-01T00-00-00Z",
                total_items=9,
                executed_item_count=1,
                approval_coverage_rate=1.0,
                execution_completion_rate=1 / 9,
            ),
            _history_entry(
                "2026-05-20T00-00-00Z",
                total_items=10,
                executed_item_count=0,
                approval_coverage_rate=0.0,
                execution_completion_rate=0.0,
            ),
            _history_entry(
                "2026-05-10T00-00-00Z",
                total_items=11,
                executed_item_count=0,
                approval_coverage_rate=0.0,
                execution_completion_rate=0.0,
            ),
            _history_entry(
                "2026-05-01T00-00-00Z",
                total_items=12,
                executed_item_count=0,
                approval_coverage_rate=0.0,
                execution_completion_rate=0.0,
            ),
        ],
    }

    packet = build_reporting_trend_packet(
        generated_at="2026-06-12T01:00:00Z",
        history_packet=history_packet,
        window_requested=3,
    )

    assert packet["window_requested"] == 3
    assert packet["window_run_count"] == 3
    assert [entry["run_stamp"] for entry in packet["runs"]] == [
        "2026-05-20T00-00-00Z",
        "2026-06-01T00-00-00Z",
        "2026-06-10T00-00-00Z",
    ]


def test_build_reporting_trend_packet_uses_full_history_when_requested_window_exceeds_visible_runs() -> None:
    history_packet = {
        "generated_at": "2026-06-12T00:00:00Z",
        "latest_run_stamp": "2026-06-10T00-00-00Z",
        "prior_run_stamp": "2026-06-01T00-00-00Z",
        "run_count": 2,
        "runs": [
            _history_entry(
                "2026-06-10T00-00-00Z",
                total_items=9,
                executed_item_count=0,
                approval_coverage_rate=0.0,
                execution_completion_rate=0.0,
            ),
            _history_entry(
                "2026-06-01T00-00-00Z",
                total_items=9,
                executed_item_count=1,
                approval_coverage_rate=1.0,
                execution_completion_rate=1 / 9,
            ),
        ],
    }

    packet = build_reporting_trend_packet(
        generated_at="2026-06-12T01:00:00Z",
        history_packet=history_packet,
        window_requested=5,
    )

    assert packet["window_requested"] == 5
    assert packet["window_run_count"] == 2
    assert [entry["run_stamp"] for entry in packet["runs"]] == [
        "2026-06-01T00-00-00Z",
        "2026-06-10T00-00-00Z",
    ]


def test_build_reporting_trend_packet_rejects_missing_reporting_metadata_inside_selected_window() -> None:
    history_packet = {
        "generated_at": "2026-06-12T00:00:00Z",
        "latest_run_stamp": "2026-06-10T00-00-00Z",
        "prior_run_stamp": "2026-06-01T00-00-00Z",
        "run_count": 3,
        "runs": [
            _history_entry(
                "2026-06-10T00-00-00Z",
                total_items=9,
                executed_item_count=0,
                approval_coverage_rate=0.0,
                execution_completion_rate=0.0,
            ),
            {
                "run_stamp": "2026-06-01T00-00-00Z",
                "dispatch_run_ref": ".omo/debt/dispatch/runs/2026-06-01T00-00-00Z.yaml",
                "reporting_ref": None,
                "reporting_exists": False,
                "report_generated_at": None,
                "total_items": None,
                "executed_item_count": None,
                "approval_coverage_rate": None,
                "execution_completion_rate": None,
            },
            _history_entry(
                "2026-05-20T00-00-00Z",
                total_items=10,
                executed_item_count=0,
                approval_coverage_rate=0.0,
                execution_completion_rate=0.0,
            ),
        ],
    }

    with pytest.raises(ValueError, match="missing reporting trend metadata for run: 2026-06-01T00-00-00Z"):
        build_reporting_trend_packet(
            generated_at="2026-06-12T01:00:00Z",
            history_packet=history_packet,
            window_requested=2,
        )


def test_build_reporting_trend_packet_selects_inclusive_range_by_run_stamp() -> None:
    history_packet = {
        "generated_at": "2026-06-12T00:00:00Z",
        "latest_run_stamp": "2026-06-10T00-00-00Z",
        "prior_run_stamp": "2026-06-01T00-00-00Z",
        "run_count": 5,
        "runs": [
            _history_entry(
                "2026-06-10T00-00-00Z",
                total_items=9,
                executed_item_count=0,
                approval_coverage_rate=0.0,
                execution_completion_rate=0.0,
            ),
            _history_entry(
                "2026-06-01T00-00-00Z",
                total_items=9,
                executed_item_count=1,
                approval_coverage_rate=1.0,
                execution_completion_rate=1 / 9,
            ),
            _history_entry(
                "2026-05-20T00-00-00Z",
                total_items=10,
                executed_item_count=0,
                approval_coverage_rate=0.0,
                execution_completion_rate=0.0,
            ),
            _history_entry(
                "2026-05-10T00-00-00Z",
                total_items=11,
                executed_item_count=0,
                approval_coverage_rate=0.0,
                execution_completion_rate=0.0,
            ),
            _history_entry(
                "2026-05-01T00-00-00Z",
                total_items=12,
                executed_item_count=0,
                approval_coverage_rate=0.0,
                execution_completion_rate=0.0,
            ),
        ],
    }

    packet = build_reporting_trend_packet(
        generated_at="2026-06-12T01:00:00Z",
        history_packet=history_packet,
        from_run_stamp_requested="2026-05-20T00-00-00Z",
        to_run_stamp_requested="2026-06-10T00-00-00Z",
    )

    assert packet["window_requested"] is None
    assert packet["from_run_stamp_requested"] == "2026-05-20T00-00-00Z"
    assert packet["to_run_stamp_requested"] == "2026-06-10T00-00-00Z"
    assert packet["window_run_count"] == 3
    assert [entry["run_stamp"] for entry in packet["runs"]] == [
        "2026-05-20T00-00-00Z",
        "2026-06-01T00-00-00Z",
        "2026-06-10T00-00-00Z",
    ]


def test_build_reporting_trend_packet_rejects_invalid_requested_range_stamp() -> None:
    history_packet = {
        "generated_at": "2026-06-12T00:00:00Z",
        "latest_run_stamp": "2026-06-10T00-00-00Z",
        "prior_run_stamp": "2026-06-01T00-00-00Z",
        "run_count": 2,
        "runs": [
            _history_entry(
                "2026-06-10T00-00-00Z",
                total_items=9,
                executed_item_count=0,
                approval_coverage_rate=0.0,
                execution_completion_rate=0.0,
            ),
            _history_entry(
                "2026-06-01T00-00-00Z",
                total_items=9,
                executed_item_count=1,
                approval_coverage_rate=1.0,
                execution_completion_rate=1 / 9,
            ),
        ],
    }

    with pytest.raises(ValueError, match="invalid from-run-stamp: 2026-06-01T00:00:00Z"):
        build_reporting_trend_packet(
            generated_at="2026-06-12T01:00:00Z",
            history_packet=history_packet,
            from_run_stamp_requested="2026-06-01T00:00:00Z",
            to_run_stamp_requested="2026-06-10T00-00-00Z",
        )


def test_build_reporting_trend_packet_rejects_missing_requested_range_stamp() -> None:
    history_packet = {
        "generated_at": "2026-06-12T00:00:00Z",
        "latest_run_stamp": "2026-06-10T00-00-00Z",
        "prior_run_stamp": "2026-06-01T00-00-00Z",
        "run_count": 2,
        "runs": [
            _history_entry(
                "2026-06-10T00-00-00Z",
                total_items=9,
                executed_item_count=0,
                approval_coverage_rate=0.0,
                execution_completion_rate=0.0,
            ),
            _history_entry(
                "2026-06-01T00-00-00Z",
                total_items=9,
                executed_item_count=1,
                approval_coverage_rate=1.0,
                execution_completion_rate=1 / 9,
            ),
        ],
    }

    with pytest.raises(ValueError, match="from-run-stamp not in history: 2026-05-20T00-00-00Z"):
        build_reporting_trend_packet(
            generated_at="2026-06-12T01:00:00Z",
            history_packet=history_packet,
            from_run_stamp_requested="2026-05-20T00-00-00Z",
            to_run_stamp_requested="2026-06-10T00-00-00Z",
        )


def test_build_reporting_trend_packet_rejects_reversed_semantic_range() -> None:
    history_packet = {
        "generated_at": "2026-06-12T00:00:00Z",
        "latest_run_stamp": "2026-06-10T00-00-00Z",
        "prior_run_stamp": "2026-06-01T00-00-00Z",
        "run_count": 3,
        "runs": [
            _history_entry(
                "2026-06-10T00-00-00Z",
                total_items=9,
                executed_item_count=0,
                approval_coverage_rate=0.0,
                execution_completion_rate=0.0,
            ),
            _history_entry(
                "2026-06-01T00-00-00Z",
                total_items=9,
                executed_item_count=1,
                approval_coverage_rate=1.0,
                execution_completion_rate=1 / 9,
            ),
            _history_entry(
                "2026-05-20T00-00-00Z",
                total_items=10,
                executed_item_count=0,
                approval_coverage_rate=0.0,
                execution_completion_rate=0.0,
            ),
        ],
    }

    with pytest.raises(ValueError, match="from-run-stamp must not be newer than to-run-stamp"):
        build_reporting_trend_packet(
            generated_at="2026-06-12T01:00:00Z",
            history_packet=history_packet,
            from_run_stamp_requested="2026-06-10T00-00-00Z",
            to_run_stamp_requested="2026-05-20T00-00-00Z",
        )


def test_render_reporting_trend_markdown_shows_trend_and_insufficient_history_states() -> None:
    trend_packet = build_reporting_trend_packet(
        generated_at="2026-06-12T01:00:00Z",
        history_packet={
            "generated_at": "2026-06-12T00:00:00Z",
            "latest_run_stamp": "2026-06-10T00-00-00Z",
            "prior_run_stamp": "2026-06-01T00-00-00Z",
            "run_count": 2,
            "runs": [
                _history_entry(
                    "2026-06-10T00-00-00Z",
                    total_items=9,
                    executed_item_count=0,
                    approval_coverage_rate=0.0,
                    execution_completion_rate=0.0,
                ),
                _history_entry(
                    "2026-06-01T00-00-00Z",
                    total_items=9,
                    executed_item_count=1,
                    approval_coverage_rate=1.0,
                    execution_completion_rate=1 / 9,
                ),
            ],
        },
    )
    insufficient_packet = build_reporting_trend_packet(
        generated_at="2026-06-12T01:00:00Z",
        history_packet={
            "generated_at": "2026-06-12T00:00:00Z",
            "latest_run_stamp": "2026-06-10T00-00-00Z",
            "prior_run_stamp": None,
            "run_count": 1,
            "runs": [
                _history_entry(
                    "2026-06-10T00-00-00Z",
                    total_items=9,
                    executed_item_count=0,
                    approval_coverage_rate=0.0,
                    execution_completion_rate=0.0,
                )
            ],
        },
    )

    trend_markdown = render_reporting_trend_markdown(trend_packet)
    insufficient_markdown = render_reporting_trend_markdown(insufficient_packet)

    assert "# Debt Reporting Trend" in trend_markdown
    assert "Trend status: trend_available" in trend_markdown
    assert "2026-06-01T00-00-00Z -> 2026-06-10T00-00-00Z" in trend_markdown
    assert "Trend status: insufficient_history" in insufficient_markdown
    assert "Trend baseline not established yet." in insufficient_markdown


def test_render_reporting_trend_markdown_includes_owner_trend_section() -> None:
    packet = {
        "generated_at": "2026-06-12T01:00:00Z",
        "trend_status": "trend_available",
        "window_requested": None,
        "from_run_stamp_requested": None,
        "to_run_stamp_requested": None,
        "window_run_count": 2,
        "oldest_run_stamp": "2026-06-01T00-00-00Z",
        "latest_run_stamp": "2026-06-10T00-00-00Z",
        "runs": [
            {
                "run_stamp": "2026-06-01T00-00-00Z",
                "dispatch_run_ref": ".omo/debt/dispatch/runs/2026-06-01T00-00-00Z.yaml",
                "reporting_ref": ".omo/debt/reporting/runs/2026-06-01T00-00-00Z/current.yaml",
                "total_items": 9,
                "executed_item_count": 0,
                "approval_coverage_rate": 0.0,
                "execution_completion_rate": 0.0,
            },
            {
                "run_stamp": "2026-06-10T00-00-00Z",
                "dispatch_run_ref": ".omo/debt/dispatch/runs/2026-06-10T00-00-00Z.yaml",
                "reporting_ref": ".omo/debt/reporting/runs/2026-06-10T00-00-00Z/current.yaml",
                "total_items": 9,
                "executed_item_count": 1,
                "approval_coverage_rate": 1.0,
                "execution_completion_rate": 1 / 9,
            },
        ],
        "intervals": [
            {
                "from_run_stamp": "2026-06-01T00-00-00Z",
                "to_run_stamp": "2026-06-10T00-00-00Z",
                "total_items_delta": 0,
                "executed_item_count_delta": 1,
                "approval_coverage_rate_delta": 1.0,
                "execution_completion_rate_delta": 1 / 9,
            }
        ],
        "owners": {
            "owners_trend_status": "owners_trend_available",
            "shared_owner_count": 1,
            "owners_excluded_count": 0,
            "compared": [
                {
                    "owner": "omo-governance",
                    "runs": [
                        {
                            "run_stamp": "2026-06-01T00-00-00Z",
                            "item_count": 2,
                            "executed_item_count": 0,
                            "approval_coverage_rate": 1.0,
                            "execution_completion_rate": 0.0,
                        },
                        {
                            "run_stamp": "2026-06-10T00-00-00Z",
                            "item_count": 3,
                            "executed_item_count": 1,
                            "approval_coverage_rate": 1.0,
                            "execution_completion_rate": 1 / 3,
                        },
                    ],
                    "intervals": [
                        {
                            "from_run_stamp": "2026-06-01T00-00-00Z",
                            "to_run_stamp": "2026-06-10T00-00-00Z",
                            "item_count_delta": 1,
                            "executed_item_count_delta": 1,
                            "approval_coverage_rate_delta": 0.0,
                            "execution_completion_rate_delta": 1 / 3,
                        }
                    ],
                }
            ],
        },
    }

    markdown = render_reporting_trend_markdown(packet)

    assert "## Owner Trend" in markdown
    assert "owners_trend_status=owners_trend_available" in markdown
    assert "shared_owner_count=1" in markdown
    assert "### Owner: omo-governance" in markdown
    assert "item_count=2" in markdown
    assert "item_count_delta=1" in markdown


def test_render_reporting_trend_markdown_includes_owner_presence_section() -> None:
    packet = {
        "generated_at": "2026-06-12T01:00:00Z",
        "trend_status": "trend_available",
        "window_requested": None,
        "from_run_stamp_requested": None,
        "to_run_stamp_requested": None,
        "window_run_count": 3,
        "oldest_run_stamp": "2026-05-20T00-00-00Z",
        "latest_run_stamp": "2026-06-10T00-00-00Z",
        "runs": [
            {
                "run_stamp": "2026-05-20T00-00-00Z",
                "dispatch_run_ref": ".omo/debt/dispatch/runs/2026-05-20T00-00-00Z.yaml",
                "reporting_ref": ".omo/debt/reporting/runs/2026-05-20T00-00-00Z/current.yaml",
                "total_items": 10,
                "executed_item_count": 0,
                "approval_coverage_rate": 0.0,
                "execution_completion_rate": 0.0,
            },
            {
                "run_stamp": "2026-06-01T00-00-00Z",
                "dispatch_run_ref": ".omo/debt/dispatch/runs/2026-06-01T00-00-00Z.yaml",
                "reporting_ref": ".omo/debt/reporting/runs/2026-06-01T00-00-00Z/current.yaml",
                "total_items": 9,
                "executed_item_count": 0,
                "approval_coverage_rate": 0.0,
                "execution_completion_rate": 0.0,
            },
            {
                "run_stamp": "2026-06-10T00-00-00Z",
                "dispatch_run_ref": ".omo/debt/dispatch/runs/2026-06-10T00-00-00Z.yaml",
                "reporting_ref": ".omo/debt/reporting/runs/2026-06-10T00-00-00Z/current.yaml",
                "total_items": 9,
                "executed_item_count": 1,
                "approval_coverage_rate": 1.0,
                "execution_completion_rate": 1 / 9,
            },
        ],
        "intervals": [
            {
                "from_run_stamp": "2026-05-20T00-00-00Z",
                "to_run_stamp": "2026-06-01T00-00-00Z",
                "total_items_delta": -1,
                "executed_item_count_delta": 0,
                "approval_coverage_rate_delta": 0.0,
                "execution_completion_rate_delta": 0.0,
            },
            {
                "from_run_stamp": "2026-06-01T00-00-00Z",
                "to_run_stamp": "2026-06-10T00-00-00Z",
                "total_items_delta": 0,
                "executed_item_count_delta": 1,
                "approval_coverage_rate_delta": 1.0,
                "execution_completion_rate_delta": 1 / 9,
            },
        ],
        "owners": {
            "owners_trend_status": "owners_trend_available",
            "shared_owner_count": 1,
            "owners_excluded_count": 1,
            "compared": [
                {
                    "owner": "omo-governance",
                    "runs": [
                        {
                            "run_stamp": "2026-05-20T00-00-00Z",
                            "item_count": 1,
                            "executed_item_count": 0,
                            "approval_coverage_rate": 0.0,
                            "execution_completion_rate": 0.0,
                        },
                        {
                            "run_stamp": "2026-06-01T00-00-00Z",
                            "item_count": 2,
                            "executed_item_count": 0,
                            "approval_coverage_rate": 0.0,
                            "execution_completion_rate": 0.0,
                        },
                        {
                            "run_stamp": "2026-06-10T00-00-00Z",
                            "item_count": 3,
                            "executed_item_count": 1,
                            "approval_coverage_rate": 1.0,
                            "execution_completion_rate": 1 / 3,
                        },
                    ],
                    "intervals": [
                        {
                            "from_run_stamp": "2026-05-20T00-00-00Z",
                            "to_run_stamp": "2026-06-01T00-00-00Z",
                            "item_count_delta": 1,
                            "executed_item_count_delta": 0,
                            "approval_coverage_rate_delta": 0.0,
                            "execution_completion_rate_delta": 0.0,
                        },
                        {
                            "from_run_stamp": "2026-06-01T00-00-00Z",
                            "to_run_stamp": "2026-06-10T00-00-00Z",
                            "item_count_delta": 1,
                            "executed_item_count_delta": 1,
                            "approval_coverage_rate_delta": 1.0,
                            "execution_completion_rate_delta": 1 / 3,
                        },
                    ],
                }
            ],
        },
        "owner_presence": {
            "presence_status": "presence_available",
            "window_run_count": 3,
            "entries": [
                {
                    "owner": "late-owner",
                    "run_count": 1,
                    "first_window_run": "2026-06-10T00-00-00Z",
                    "last_window_run": "2026-06-10T00-00-00Z",
                    "in_first_window_run": False,
                    "in_last_window_run": True,
                }
            ],
        },
    }

    markdown = render_reporting_trend_markdown(packet)

    assert "## Owner Presence" in markdown
    assert "presence_status=presence_available" in markdown
    assert "window_run_count=3" in markdown
    assert "### Presence Owner: late-owner" in markdown
    assert "run_count=1" in markdown
    assert "in_last_window_run=True" in markdown


def test_render_reporting_trend_markdown_includes_execution_progress_section() -> None:
    packet = {
        "generated_at": "2026-06-12T01:00:00Z",
        "trend_status": "trend_available",
        "window_requested": None,
        "from_run_stamp_requested": None,
        "to_run_stamp_requested": None,
        "window_run_count": 3,
        "oldest_run_stamp": "2026-05-20T00-00-00Z",
        "latest_run_stamp": "2026-06-10T00-00-00Z",
        "runs": [],
        "intervals": [],
        "owners": None,
        "owner_presence": None,
        "execution_progress": {
            "progress_status": "progress_available",
            "anchor_run_stamp": "2026-05-20T00-00-00Z",
            "baseline_open_item_count": 10,
            "runs": [
                {
                    "run_stamp": "2026-05-20T00-00-00Z",
                    "open_item_count": 10,
                    "open_item_delta_vs_baseline": 0,
                    "open_item_ratio_vs_baseline": 1.0,
                },
                {
                    "run_stamp": "2026-06-10T00-00-00Z",
                    "open_item_count": 5,
                    "open_item_delta_vs_baseline": -5,
                    "open_item_ratio_vs_baseline": 0.5,
                },
            ],
        },
    }

    markdown = render_reporting_trend_markdown(packet)

    assert "## Execution Progress" in markdown
    assert "progress_status=progress_available" in markdown
    assert "anchor_run_stamp=2026-05-20T00-00-00Z" in markdown
    assert "baseline_open_item_count=10" in markdown
    assert "### Progress Run: 2026-06-10T00-00-00Z" in markdown
    assert "open_item_delta_vs_baseline=-5" in markdown
    assert "open_item_ratio_vs_baseline=0.5" in markdown


def test_render_reporting_trend_markdown_includes_state_progress_section() -> None:
    packet = {
        "generated_at": "2026-06-12T01:00:00Z",
        "trend_status": "trend_available",
        "window_requested": None,
        "from_run_stamp_requested": None,
        "to_run_stamp_requested": None,
        "window_run_count": 2,
        "oldest_run_stamp": "2026-06-01T00-00-00Z",
        "latest_run_stamp": "2026-06-10T00-00-00Z",
        "runs": [],
        "intervals": [],
        "owners": None,
        "owner_presence": None,
        "execution_progress": None,
        "state_progress": {
            "state_progress_status": "state_progress_available",
            "anchor_run_stamp": "2026-06-01T00-00-00Z",
            "baseline_pending_approval": 2,
            "runs": [
                {
                    "run_stamp": "2026-06-01T00-00-00Z",
                    "pending_approval": 2,
                    "ready_to_execute": 6,
                    "executed": 1,
                    "pending_approval_delta_vs_baseline": 0,
                },
                {
                    "run_stamp": "2026-06-10T00-00-00Z",
                    "pending_approval": 1,
                    "ready_to_execute": 4,
                    "executed": 3,
                    "pending_approval_delta_vs_baseline": -1,
                },
            ],
        },
    }

    markdown = render_reporting_trend_markdown(packet)

    assert "## State Progress" in markdown
    assert "state_progress_status=state_progress_available" in markdown
    assert "baseline_pending_approval=2" in markdown
    assert "### State Run: 2026-06-10T00-00-00Z" in markdown
    assert "pending_approval_delta_vs_baseline=-1" in markdown
