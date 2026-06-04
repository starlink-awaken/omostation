from __future__ import annotations

from omo.omo_debt_reporting import build_reporting_packet, render_reporting_markdown


def _campaign_packet() -> dict[str, object]:
    return {
        "generated_at": "2026-06-11T00:00:00Z",
        "dispatch_run_ref": ".omo/debt/dispatch/runs/2026-06-10T00-00-00Z.yaml",
        "run_stamp": "2026-06-10T00-00-00Z",
        "summary": {
            "owner_count": 2,
            "total_items": 3,
            "state_counts": {
                "pending_approval": 1,
                "ready_to_execute": 1,
                "executed": 1,
            },
        },
        "owners": [
            {
                "owner": "sharedbrain-governance",
                "item_count": 2,
                "state_counts": {
                    "pending_approval": 1,
                    "ready_to_execute": 1,
                    "executed": 0,
                },
                "entries": [
                    {
                        "id": "SB_DECOMPOSITION",
                        "gate_level": "gate",
                        "campaign_state": "pending_approval",
                        "command": "python3 scripts/omo_debt.py revalidate ...",
                    },
                    {
                        "id": "SB_UNTESTED_PKGS",
                        "gate_level": "watchlist",
                        "campaign_state": "ready_to_execute",
                        "command": "python3 scripts/omo_debt.py revalidate ...",
                    },
                ],
            },
            {
                "owner": "omo-governance",
                "item_count": 1,
                "state_counts": {
                    "pending_approval": 0,
                    "ready_to_execute": 0,
                    "executed": 1,
                },
                "entries": [
                    {
                        "id": "SB_GATE_REVIEW",
                        "gate_level": "gate",
                        "campaign_state": "executed",
                        "execution_record_ref": ".omo/debt/dispatch/executions/2026-06-10T00-00-00Z/SB_GATE_REVIEW.yaml",
                        "command": "python3 scripts/omo_debt.py revalidate ...",
                    }
                ],
            },
        ],
    }


def test_build_reporting_packet_summarizes_counts_and_rates() -> None:
    packet = build_reporting_packet(_campaign_packet())

    assert packet["dispatch_run_ref"] == ".omo/debt/dispatch/runs/2026-06-10T00-00-00Z.yaml"
    assert packet["summary"] == {
        "owner_count": 2,
        "total_items": 3,
        "state_counts": {
            "pending_approval": 1,
            "ready_to_execute": 1,
            "executed": 1,
        },
        "gate_item_count": 2,
        "approved_gate_item_count": 1,
        "approval_coverage_rate": 0.5,
        "executed_item_count": 1,
        "execution_completion_rate": 1 / 3,
    }

    owner = packet["owners"][0]
    assert owner == {
        "owner": "sharedbrain-governance",
        "item_count": 2,
        "state_counts": {
            "pending_approval": 1,
            "ready_to_execute": 1,
            "executed": 0,
        },
        "gate_item_count": 1,
        "approved_gate_item_count": 0,
        "approval_coverage_rate": 0.0,
        "executed_item_count": 0,
        "execution_completion_rate": 0.0,
    }


def test_build_reporting_packet_uses_default_rates_for_empty_denominators() -> None:
    packet = build_reporting_packet(
        {
            "generated_at": "2026-06-11T00:00:00Z",
            "dispatch_run_ref": ".omo/debt/dispatch/runs/2026-06-10T00-00-00Z.yaml",
            "run_stamp": "2026-06-10T00-00-00Z",
            "summary": {
                "owner_count": 1,
                "total_items": 0,
                "state_counts": {
                    "pending_approval": 0,
                    "ready_to_execute": 0,
                    "executed": 0,
                },
            },
            "owners": [
                {
                    "owner": "empty-owner",
                    "item_count": 0,
                    "state_counts": {
                        "pending_approval": 0,
                        "ready_to_execute": 0,
                        "executed": 0,
                    },
                    "entries": [],
                }
            ],
        }
    )

    assert packet["summary"]["approval_coverage_rate"] == 1.0
    assert packet["summary"]["execution_completion_rate"] == 0.0
    assert packet["owners"][0]["approval_coverage_rate"] == 1.0
    assert packet["owners"][0]["execution_completion_rate"] == 0.0


def test_render_reporting_markdown_shows_summary_and_owner_rollups() -> None:
    markdown = render_reporting_markdown(build_reporting_packet(_campaign_packet()))

    assert "# Debt Reporting Packet" in markdown
    assert "Approval coverage: 0.50" in markdown
    assert "Execution completion: 0.33" in markdown
    assert "## Owner: sharedbrain-governance" in markdown
    assert "gate_items=1, approved_gate_items=0" in markdown
