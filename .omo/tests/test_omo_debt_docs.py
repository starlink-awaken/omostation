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
