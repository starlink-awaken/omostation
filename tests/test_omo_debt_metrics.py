from __future__ import annotations

from pathlib import Path

from omo.omo_debt_metrics import compute_debt_metrics
from omo.omo_debt_registry import DebtItem, load_debt_ledger


def test_load_debt_ledger_returns_seed_items() -> None:
    ledger = load_debt_ledger(Path(".omo"))

    assert [item.id for item in ledger.items] == [
        "D2_CI_E2E",
        "D3_EU_PRICING",
        "SB_DECOMPOSITION",
        "SB_UNTESTED_PKGS",
        "SB_ORPHANED_TASKS",
        "SB_ROOT_CLEANUP",
        "SB_BRIDGE_FIX",
        "SB_PROJECTS_YAML",
        "SB_PHASE17_PLAN",
    ]


def test_compute_debt_metrics_flags_overdue_and_gate_items() -> None:
    ledger = load_debt_ledger(Path(".omo"))

    metrics = compute_debt_metrics(ledger.items, now="2026-06-10T00:00:00Z")

    assert metrics.debt_watchlist_count >= 1
    assert metrics.debt_gate_count == 0
    assert metrics.pointer_entropy > 0
    assert metrics.time_entropy > 0
    assert "D2_CI_E2E" in metrics.closed_item_ids
    assert "D3_EU_PRICING" in metrics.closed_item_ids


def test_compute_debt_metrics_flags_stale_evidence_when_refs_are_newer_than_last_reviewed(
    tmp_path: Path,
) -> None:
    evidence = tmp_path / "evidence.md"
    evidence.write_text("fresh evidence\n", encoding="utf-8")
    mitigation = tmp_path / "mitigation.md"
    mitigation.write_text("mitigation\n", encoding="utf-8")

    item = DebtItem(
        id="LEDGER_STALE",
        title="Ledger stale",
        dimension="architecture",
        subdimension="boundaries",
        domain="workspace",
        scope="cross_project",
        severity="medium",
        weight=0.5,
        entropy_class="pointer",
        lifecycle_state="classified",
        owner="platform-governance",
        affected_roots=("projects/demo",),
        evidence_refs=("evidence.md",),
        mitigation_refs=("mitigation.md",),
        opened_at="2026-06-01T00:00:00Z",
        last_reviewed_at="2026-06-01T00:00:00Z",
        next_review_at="2026-06-20T00:00:00Z",
        gate_level="none",
        history=(),
    )

    metrics = compute_debt_metrics(
        (item,),
        now="2026-06-10T00:00:00Z",
        repo_root=tmp_path,
    )

    assert metrics.pointer_entropy == 1.0
    assert metrics.time_entropy == 0.0
