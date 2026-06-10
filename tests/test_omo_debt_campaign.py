from __future__ import annotations

from omo.omo_debt_campaign import build_campaign_packet, render_campaign_markdown


def _dispatch_run() -> dict[str, object]:
    return {
        "dispatched_at": "2026-06-10T00:00:00Z",
        "owners": [
            {
                "owner": "sharedbrain-governance",
                "item_count": 2,
                "summary": {"total_count": 2, "lane_counts": {"revalidate_now": 2}},
                "entries": [
                    {
                        "id": "SB_DECOMPOSITION",
                        "owner": "sharedbrain-governance",
                        "title": "SharedBrain decomposition remains partially governed",
                        "primary_lane": "revalidate_now",
                        "gate_level": "gate",
                        "reason": "stale_due_item",
                        "command": "python3 scripts/omo_debt.py revalidate --omo-dir .omo --id SB_DECOMPOSITION --reviewed-at 2026-06-10T00:00:00Z --dispatch-run-ref .omo/debt/dispatch/runs/2026-06-10T00-00-00Z.yaml",
                    },
                    {
                        "id": "SB_UNTESTED_PKGS",
                        "owner": "sharedbrain-governance",
                        "title": "SharedBrain-adjacent packages lack test baselines",
                        "primary_lane": "revalidate_now",
                        "gate_level": "watchlist",
                        "reason": "stale_due_item",
                        "command": "python3 scripts/omo_debt.py revalidate --omo-dir .omo --id SB_UNTESTED_PKGS --reviewed-at 2026-06-10T00:00:00Z --dispatch-run-ref .omo/debt/dispatch/runs/2026-06-10T00-00-00Z.yaml",
                    },
                ],
            }
        ],
        "summary": {"owner_count": 1, "total_dispatched_items": 2},
    }


def test_build_campaign_packet_classifies_pending_ready_and_executed() -> None:
    dispatch_run_ref = ".omo/debt/dispatch/runs/2026-06-10T00-00-00Z.yaml"
    packet = build_campaign_packet(
        run_packet=_dispatch_run(),
        dispatch_run_ref=dispatch_run_ref,
        generated_at="2026-06-11T00:00:00Z",
        approval_lookup={"SB_DECOMPOSITION": True},
        execution_lookup={
            "SB_UNTESTED_PKGS": ".omo/debt/dispatch/executions/2026-06-10T00-00-00Z/SB_UNTESTED_PKGS.yaml"
        },
    )

    assert packet["run_stamp"] == "2026-06-10T00-00-00Z"
    assert packet["summary"]["state_counts"] == {
        "pending_approval": 0,
        "ready_to_execute": 1,
        "executed": 1,
    }
    owner = packet["owners"][0]
    assert owner["state_counts"] == {"pending_approval": 0, "ready_to_execute": 1, "executed": 1}
    assert owner["entries"][0]["campaign_state"] == "ready_to_execute"
    assert owner["entries"][1]["campaign_state"] == "executed"
    assert owner["entries"][1]["execution_record_ref"] == (
        ".omo/debt/dispatch/executions/2026-06-10T00-00-00Z/SB_UNTESTED_PKGS.yaml"
    )


def test_render_campaign_markdown_groups_entries_by_state() -> None:
    packet = build_campaign_packet(
        run_packet=_dispatch_run(),
        dispatch_run_ref=".omo/debt/dispatch/runs/2026-06-10T00-00-00Z.yaml",
        generated_at="2026-06-11T00:00:00Z",
        approval_lookup={},
        execution_lookup={},
    )

    markdown = render_campaign_markdown(packet)
    assert "# Debt Campaign Packet" in markdown
    assert "pending_approval=1, ready_to_execute=1, executed=0" in markdown
    assert "### Pending Approval" in markdown
    assert "### Ready To Execute" in markdown
