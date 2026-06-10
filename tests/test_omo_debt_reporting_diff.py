from __future__ import annotations

from omo.omo_debt_reporting_diff import build_reporting_diff_packet, render_reporting_diff_markdown


def _owner_packet(
    owner: str,
    *,
    item_count: int,
    pending_approval: int,
    ready_to_execute: int,
    executed: int,
    gate_item_count: int,
    approved_gate_item_count: int,
    approval_coverage_rate: float,
    executed_item_count: int,
    execution_completion_rate: float,
) -> dict[str, object]:
    return {
        "owner": owner,
        "item_count": item_count,
        "state_counts": {
            "pending_approval": pending_approval,
            "ready_to_execute": ready_to_execute,
            "executed": executed,
        },
        "gate_item_count": gate_item_count,
        "approved_gate_item_count": approved_gate_item_count,
        "approval_coverage_rate": approval_coverage_rate,
        "executed_item_count": executed_item_count,
        "execution_completion_rate": execution_completion_rate,
    }


def _reporting_packet(
    run_stamp: str,
    *,
    dispatch_run_ref: str,
    total_items: int,
    pending_approval: int,
    ready_to_execute: int,
    executed: int,
    gate_item_count: int,
    approved_gate_item_count: int,
    approval_coverage_rate: float,
    executed_item_count: int,
    execution_completion_rate: float,
    owners: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    return {
        "generated_at": "2026-06-12T00:00:00Z",
        "dispatch_run_ref": dispatch_run_ref,
        "run_stamp": run_stamp,
        "summary": {
            "owner_count": 4,
            "total_items": total_items,
            "state_counts": {
                "pending_approval": pending_approval,
                "ready_to_execute": ready_to_execute,
                "executed": executed,
            },
            "gate_item_count": gate_item_count,
            "approved_gate_item_count": approved_gate_item_count,
            "approval_coverage_rate": approval_coverage_rate,
            "executed_item_count": executed_item_count,
            "execution_completion_rate": execution_completion_rate,
        },
        "owners": owners or [],
    }


def test_build_reporting_diff_packet_computes_summary_deltas() -> None:
    latest = _reporting_packet(
        "2026-06-10T00-00-00Z",
        dispatch_run_ref=".omo/debt/dispatch/runs/2026-06-10T00-00-00Z.yaml",
        total_items=9,
        pending_approval=0,
        ready_to_execute=7,
        executed=2,
        gate_item_count=1,
        approved_gate_item_count=1,
        approval_coverage_rate=1.0,
        executed_item_count=2,
        execution_completion_rate=2 / 9,
    )
    prior = _reporting_packet(
        "2026-06-01T00-00-00Z",
        dispatch_run_ref=".omo/debt/dispatch/runs/2026-06-01T00-00-00Z.yaml",
        total_items=9,
        pending_approval=1,
        ready_to_execute=8,
        executed=0,
        gate_item_count=1,
        approved_gate_item_count=0,
        approval_coverage_rate=0.0,
        executed_item_count=0,
        execution_completion_rate=0.0,
    )

    packet = build_reporting_diff_packet(
        generated_at="2026-06-12T01:00:00Z",
        latest_packet=latest,
        prior_packet=prior,
    )

    assert packet["diff_status"] == "diff_available"
    assert packet["latest_run_stamp"] == "2026-06-10T00-00-00Z"
    assert packet["prior_run_stamp"] == "2026-06-01T00-00-00Z"
    assert packet["owners"] == {"compared": [], "added": [], "removed": []}
    assert packet["summary_diff"]["total_items"] == {"latest": 9, "prior": 9, "delta": 0}
    assert packet["summary_diff"]["state_counts"]["executed"] == {"latest": 2, "prior": 0, "delta": 2}
    assert packet["summary_diff"]["approval_coverage_rate"] == {"latest": 1.0, "prior": 0.0, "delta": 1.0}
    assert "owner_count" not in packet["summary_diff"]


def test_build_reporting_diff_packet_matches_shared_owners_by_name() -> None:
    latest = _reporting_packet(
        "2026-06-10T00-00-00Z",
        dispatch_run_ref=".omo/debt/dispatch/runs/2026-06-10T00-00-00Z.yaml",
        total_items=9,
        pending_approval=0,
        ready_to_execute=7,
        executed=2,
        gate_item_count=1,
        approved_gate_item_count=1,
        approval_coverage_rate=1.0,
        executed_item_count=2,
        execution_completion_rate=2 / 9,
        owners=[
            _owner_packet(
                "omo-governance",
                item_count=3,
                pending_approval=0,
                ready_to_execute=2,
                executed=1,
                gate_item_count=0,
                approved_gate_item_count=0,
                approval_coverage_rate=1.0,
                executed_item_count=1,
                execution_completion_rate=1 / 3,
            ),
            _owner_packet(
                "commerce-governance",
                item_count=2,
                pending_approval=0,
                ready_to_execute=2,
                executed=0,
                gate_item_count=1,
                approved_gate_item_count=1,
                approval_coverage_rate=1.0,
                executed_item_count=0,
                execution_completion_rate=0.0,
            ),
        ],
    )
    prior = _reporting_packet(
        "2026-06-01T00-00-00Z",
        dispatch_run_ref=".omo/debt/dispatch/runs/2026-06-01T00-00-00Z.yaml",
        total_items=9,
        pending_approval=1,
        ready_to_execute=8,
        executed=0,
        gate_item_count=1,
        approved_gate_item_count=0,
        approval_coverage_rate=0.0,
        executed_item_count=0,
        execution_completion_rate=0.0,
        owners=[
            _owner_packet(
                "commerce-governance",
                item_count=1,
                pending_approval=1,
                ready_to_execute=0,
                executed=0,
                gate_item_count=1,
                approved_gate_item_count=0,
                approval_coverage_rate=0.0,
                executed_item_count=0,
                execution_completion_rate=0.0,
            ),
            _owner_packet(
                "omo-governance",
                item_count=2,
                pending_approval=1,
                ready_to_execute=1,
                executed=0,
                gate_item_count=0,
                approved_gate_item_count=0,
                approval_coverage_rate=1.0,
                executed_item_count=0,
                execution_completion_rate=0.0,
            ),
        ],
    )

    packet = build_reporting_diff_packet(
        generated_at="2026-06-12T01:00:00Z",
        latest_packet=latest,
        prior_packet=prior,
    )

    assert [entry["owner"] for entry in packet["owners"]["compared"]] == [
        "commerce-governance",
        "omo-governance",
    ]
    assert packet["owners"]["compared"][0]["item_count"] == {"latest": 2, "prior": 1, "delta": 1}
    assert packet["owners"]["compared"][1]["executed_item_count"] == {"latest": 1, "prior": 0, "delta": 1}
    assert packet["owners"]["added"] == []
    assert packet["owners"]["removed"] == []


def test_build_reporting_diff_packet_surfaces_added_and_removed_owners() -> None:
    latest = _reporting_packet(
        "2026-06-10T00-00-00Z",
        dispatch_run_ref=".omo/debt/dispatch/runs/2026-06-10T00-00-00Z.yaml",
        total_items=9,
        pending_approval=0,
        ready_to_execute=7,
        executed=2,
        gate_item_count=1,
        approved_gate_item_count=1,
        approval_coverage_rate=1.0,
        executed_item_count=2,
        execution_completion_rate=2 / 9,
        owners=[
            _owner_packet(
                "commerce-governance",
                item_count=2,
                pending_approval=0,
                ready_to_execute=2,
                executed=0,
                gate_item_count=1,
                approved_gate_item_count=1,
                approval_coverage_rate=1.0,
                executed_item_count=0,
                execution_completion_rate=0.0,
            ),
            _owner_packet(
                "new-owner",
                item_count=1,
                pending_approval=0,
                ready_to_execute=1,
                executed=0,
                gate_item_count=0,
                approved_gate_item_count=0,
                approval_coverage_rate=1.0,
                executed_item_count=0,
                execution_completion_rate=0.0,
            ),
        ],
    )
    prior = _reporting_packet(
        "2026-06-01T00-00-00Z",
        dispatch_run_ref=".omo/debt/dispatch/runs/2026-06-01T00-00-00Z.yaml",
        total_items=9,
        pending_approval=1,
        ready_to_execute=8,
        executed=0,
        gate_item_count=1,
        approved_gate_item_count=0,
        approval_coverage_rate=0.0,
        executed_item_count=0,
        execution_completion_rate=0.0,
        owners=[
            _owner_packet(
                "commerce-governance",
                item_count=1,
                pending_approval=1,
                ready_to_execute=0,
                executed=0,
                gate_item_count=1,
                approved_gate_item_count=0,
                approval_coverage_rate=0.0,
                executed_item_count=0,
                execution_completion_rate=0.0,
            ),
            _owner_packet(
                "old-owner",
                item_count=2,
                pending_approval=1,
                ready_to_execute=1,
                executed=0,
                gate_item_count=0,
                approved_gate_item_count=0,
                approval_coverage_rate=1.0,
                executed_item_count=0,
                execution_completion_rate=0.0,
            ),
        ],
    )

    packet = build_reporting_diff_packet(
        generated_at="2026-06-12T01:00:00Z",
        latest_packet=latest,
        prior_packet=prior,
    )

    assert [entry["owner"] for entry in packet["owners"]["compared"]] == ["commerce-governance"]
    assert packet["owners"]["added"] == [{"owner": "new-owner"}]
    assert packet["owners"]["removed"] == [{"owner": "old-owner"}]


def test_build_reporting_diff_packet_writes_no_prior_run_state() -> None:
    latest = _reporting_packet(
        "2026-06-10T00-00-00Z",
        dispatch_run_ref=".omo/debt/dispatch/runs/2026-06-10T00-00-00Z.yaml",
        total_items=9,
        pending_approval=1,
        ready_to_execute=8,
        executed=0,
        gate_item_count=1,
        approved_gate_item_count=0,
        approval_coverage_rate=0.0,
        executed_item_count=0,
        execution_completion_rate=0.0,
    )

    packet = build_reporting_diff_packet(
        generated_at="2026-06-12T01:00:00Z",
        latest_packet=latest,
        prior_packet=None,
    )

    assert packet["diff_status"] == "no_prior_run"
    assert packet["prior_run_stamp"] is None
    assert packet["prior_dispatch_run_ref"] is None
    assert packet["owners"] is None
    assert packet["summary_diff"]["total_items"] == {"latest": 9, "prior": None, "delta": None}
    assert packet["summary_diff"]["state_counts"]["pending_approval"] == {
        "latest": 1,
        "prior": None,
        "delta": None,
    }


def test_render_reporting_diff_markdown_shows_diff_and_no_prior_states() -> None:
    latest = _reporting_packet(
        "2026-06-10T00-00-00Z",
        dispatch_run_ref=".omo/debt/dispatch/runs/2026-06-10T00-00-00Z.yaml",
        total_items=9,
        pending_approval=0,
        ready_to_execute=7,
        executed=2,
        gate_item_count=1,
        approved_gate_item_count=1,
        approval_coverage_rate=1.0,
        executed_item_count=2,
        execution_completion_rate=2 / 9,
    )
    prior = _reporting_packet(
        "2026-06-01T00-00-00Z",
        dispatch_run_ref=".omo/debt/dispatch/runs/2026-06-01T00-00-00Z.yaml",
        total_items=9,
        pending_approval=1,
        ready_to_execute=8,
        executed=0,
        gate_item_count=1,
        approved_gate_item_count=0,
        approval_coverage_rate=0.0,
        executed_item_count=0,
        execution_completion_rate=0.0,
    )

    markdown = render_reporting_diff_markdown(
        build_reporting_diff_packet(
            generated_at="2026-06-12T01:00:00Z",
            latest_packet=latest,
            prior_packet=prior,
        )
    )
    no_prior_markdown = render_reporting_diff_markdown(
        build_reporting_diff_packet(
            generated_at="2026-06-12T01:00:00Z",
            latest_packet=latest,
            prior_packet=None,
        )
    )

    assert "# Debt Reporting Diff" in markdown
    assert "Diff status: diff_available" in markdown
    assert "approval_coverage_rate: latest=1.0, prior=0.0, delta=1.0" in markdown
    assert "Diff status: no_prior_run" in no_prior_markdown
    assert "Prior baseline not established yet." in no_prior_markdown


def test_render_reporting_diff_markdown_shows_owner_sections() -> None:
    latest = _reporting_packet(
        "2026-06-10T00-00-00Z",
        dispatch_run_ref=".omo/debt/dispatch/runs/2026-06-10T00-00-00Z.yaml",
        total_items=9,
        pending_approval=0,
        ready_to_execute=7,
        executed=2,
        gate_item_count=1,
        approved_gate_item_count=1,
        approval_coverage_rate=1.0,
        executed_item_count=2,
        execution_completion_rate=2 / 9,
        owners=[
            _owner_packet(
                "commerce-governance",
                item_count=2,
                pending_approval=0,
                ready_to_execute=2,
                executed=0,
                gate_item_count=1,
                approved_gate_item_count=1,
                approval_coverage_rate=1.0,
                executed_item_count=0,
                execution_completion_rate=0.0,
            ),
            _owner_packet(
                "new-owner",
                item_count=1,
                pending_approval=0,
                ready_to_execute=1,
                executed=0,
                gate_item_count=0,
                approved_gate_item_count=0,
                approval_coverage_rate=1.0,
                executed_item_count=0,
                execution_completion_rate=0.0,
            ),
        ],
    )
    prior = _reporting_packet(
        "2026-06-01T00-00-00Z",
        dispatch_run_ref=".omo/debt/dispatch/runs/2026-06-01T00-00-00Z.yaml",
        total_items=9,
        pending_approval=1,
        ready_to_execute=8,
        executed=0,
        gate_item_count=1,
        approved_gate_item_count=0,
        approval_coverage_rate=0.0,
        executed_item_count=0,
        execution_completion_rate=0.0,
        owners=[
            _owner_packet(
                "commerce-governance",
                item_count=1,
                pending_approval=1,
                ready_to_execute=0,
                executed=0,
                gate_item_count=1,
                approved_gate_item_count=0,
                approval_coverage_rate=0.0,
                executed_item_count=0,
                execution_completion_rate=0.0,
            ),
            _owner_packet(
                "old-owner",
                item_count=2,
                pending_approval=1,
                ready_to_execute=1,
                executed=0,
                gate_item_count=0,
                approved_gate_item_count=0,
                approval_coverage_rate=1.0,
                executed_item_count=0,
                execution_completion_rate=0.0,
            ),
        ],
    )

    markdown = render_reporting_diff_markdown(
        build_reporting_diff_packet(
            generated_at="2026-06-12T01:00:00Z",
            latest_packet=latest,
            prior_packet=prior,
        )
    )

    assert "## Owner Diff" in markdown
    assert "### Shared owners" in markdown
    assert "#### commerce-governance" in markdown
    assert "- item_count: latest=2, prior=1, delta=1" in markdown
    assert "- pending_approval: latest=0, prior=1, delta=-1" in markdown
    assert "- ready_to_execute: latest=2, prior=0, delta=2" in markdown
    assert "- executed: latest=0, prior=0, delta=0" in markdown
    assert "- gate_item_count: latest=1, prior=1, delta=0" in markdown
    assert "- approved_gate_item_count: latest=1, prior=0, delta=1" in markdown
    assert "- approval_coverage_rate: latest=1.0, prior=0.0, delta=1.0" in markdown
    assert "- executed_item_count: latest=0, prior=0, delta=0" in markdown
    assert "- execution_completion_rate: latest=0.0, prior=0.0, delta=0.0" in markdown
    assert "### Added owners" in markdown
    assert "- `new-owner`" in markdown
    assert "### Removed owners" in markdown
    assert "- `old-owner`" in markdown
