from __future__ import annotations

from pathlib import Path


def test_omo_agent_documents_debt_refresh_flow() -> None:
    content = Path(".omo/AGENT.md").read_text(encoding="utf-8")

    assert "python3 scripts/omo_debt.py refresh --omo-dir .omo" in content
    assert "python3 scripts/omo_debt.py dispatch --omo-dir .omo --now" in content
    assert ".omo/debt/review-queue/current.yaml" in content
    assert ".omo/debt/action-packet/current.yaml" in content
    assert ".omo/debt/action-packet/current.md" in content
    assert ".omo/debt/owner-routing/current.yaml" in content
    assert ".omo/debt/owner-routing/current.md" in content
    assert ".omo/debt/dispatch/current.yaml" in content
    assert ".omo/debt/dispatch/current.md" in content
    assert ".omo/debt/dispatch/runs/" in content
    assert "owner routing" in content.lower()
    assert "formal surfaced handoff" in content.lower()
    assert "initial_review_required" in content
    assert "command template" in content.lower()
    assert "shell example" in content.lower()
    assert "freezes commands to dispatched_at" in content.lower()
    assert "duplicate timestamp" in content.lower()
    assert "no overwrite" in content.lower()
    assert "revalidate now" in content.lower()
    assert "schedule now" in content.lower()
    assert "watch only" in content.lower()
    assert "unscheduled debts" in content.lower()
    assert "escalation candidates" in content.lower()
    assert "bash bin/verify-omo.sh" in content
    assert "overdue review count" in content
    assert "next-review queue" in content
    assert "python3 scripts/omo_debt.py approve --omo-dir .omo" in content
    assert ".omo/debt/approvals/<ITEM_ID>/current.yaml" in content
    assert "gate-level dispatched revalidate items" in content.lower()
    assert "execute_revalidate" in content
    assert "stale approval mismatch" in content.lower()
    assert "dispatch run binding" in content.lower()
    assert "--dispatch-run-ref" in content
    assert ".omo/debt/dispatch/executions/<RUN_STAMP>/" in content
    assert "stale dispatched commands fail closed" in content.lower()
    assert "python3 scripts/omo_debt.py campaign --omo-dir .omo" in content
    assert ".omo/debt/campaign/current.yaml" in content
    assert "pending_approval" in content
    assert "ready_to_execute" in content
    assert "executed" in content
    assert "python3 scripts/omo_debt.py report --omo-dir .omo" in content
    assert "python3 scripts/sync_omo_state.py --omo-dir .omo" in content
    assert ".omo/debt/reporting/current.yaml" in content
    assert ".omo/debt/reporting/runs/<RUN_STAMP>/current.yaml" in content
    assert "campaign_ref" in content
    assert "reporting_ref" in content
    assert "debt_reporting_ref" in content
    assert "dashboard = debt health" in content.lower()
    assert "campaign = coordination detail" in content.lower()
    assert "reporting = compact progress rollup" in content.lower()
    assert "approval coverage" in content.lower()
    assert "execution completion" in content.lower()
    assert "latest-run compact rollup" in content.lower()
    assert "not cross-run history" in content.lower()
    assert "python3 scripts/omo_debt.py report-history --omo-dir .omo" in content
    assert ".omo/debt/reporting/history/current.yaml" in content
    assert ".omo/debt/reporting/history/current.md" in content
    assert "latest run" in content.lower()
    assert "prior run" in content.lower()
    assert "prerequisite for later diff work" in content.lower()
    assert "python3 scripts/omo_debt.py report-diff --omo-dir .omo" in content
    assert ".omo/debt/reporting/diff/current.yaml" in content
    assert ".omo/debt/reporting/diff/current.md" in content
    assert "no_prior_run" in content
    assert "owners.compared" in content
    assert "owners.added" in content
    assert "owners.removed" in content
    assert "shared owners" in content.lower()
    assert "added owners" in content.lower()
    assert "removed owners" in content.lower()
    assert "python3 scripts/omo_debt.py report-trend --omo-dir .omo" in content
    assert "python3 scripts/omo_debt.py report-trend --omo-dir .omo --last <N>" in content
    assert "python3 scripts/omo_debt.py report-trend --omo-dir .omo --from-run-stamp <STAMP> --to-run-stamp <STAMP>" in content
    assert ".omo/debt/reporting/trend/current.yaml" in content
    assert ".omo/debt/reporting/trend/current.md" in content
    assert "trend_status" in content
    assert "insufficient_history" in content
    assert "trend_available" in content
    assert "window_requested" in content
    assert "from_run_stamp_requested" in content
    assert "to_run_stamp_requested" in content
    assert "oldest-to-newest" in content.lower()
    assert "most recent n runs" in content.lower()
    assert "before oldest-to-newest rendering" in content.lower()
    assert "inclusive" in content.lower()
    assert "cannot be combined with --last" in content.lower()
    assert "total_items" in content
    assert "executed_item_count" in content
    assert "approval_coverage_rate" in content
    assert "execution_completion_rate" in content
    assert "owner trend" in content.lower()
    assert "owners_trend_status" in content
    assert "owners_trend_available" in content
    assert "no_shared_owners" in content
    assert "shared_owner_count" in content
    assert "owners_excluded_count" in content
    assert "shared-owner only" in content.lower()
    assert "selected window" in content.lower()
    assert "item_count" in content
    assert "owners stays null" in content.lower()
    assert "sparse gaps" in content.lower()
    assert "slope math" in content.lower()
    assert "refresh -> dispatch -> campaign -> report -> sync -> verify" in content.lower()
    assert "drift" in content.lower()
    assert "silent success" in content.lower()
