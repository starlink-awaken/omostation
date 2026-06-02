from __future__ import annotations

import pytest

from scripts.omo_debt_reporting_trend import build_reporting_trend_packet, render_reporting_trend_markdown


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
