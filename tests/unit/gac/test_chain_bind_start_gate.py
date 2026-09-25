"""start_requires_bet must not be stricter than the closeout it feeds (G5).

``evaluate_closeout`` already excuses governance-evolve workflows from a business
bet when the ledger carries a governance bet (G8/T10-08). Start did not, so a
governance self-evolution run could open only through a recorded gate waiver —
70 of the workspace's 136 waiver files are that one line. These tests pin the
two ends to the same predicate and pin the exemption against widening.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
CHAIN_MOD = ROOT / "bin/plan/chain_bind.py"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


BIND = _load(CHAIN_MOD, "chain_bind_start_gate")


def _workspace(tmp_path: Path, bets: list[dict]) -> Path:
    ledger = tmp_path / "docs/plans/3y-bet-ledger.yaml"
    ledger.parent.mkdir(parents=True, exist_ok=True)
    ledger.write_text(yaml.safe_dump({"bets": bets}, allow_unicode=True), encoding="utf-8")
    return tmp_path


def _governance_ledger(tmp_path: Path) -> Path:
    return _workspace(tmp_path, [{"id": "BET-Y2Q3-T10-202", "track": "T10-MATURITY", "status": "in_progress"}])


def _business_only_ledger(tmp_path: Path) -> Path:
    return _workspace(tmp_path, [{"id": "BET-Y2Q3-T7-01", "track": "T7-DOC", "status": "in_progress"}])


def test_governance_evolve_start_is_exempt_when_a_governance_bet_exists(tmp_path: Path) -> None:
    verdict = BIND.start_requires_bet("governance-audit", "", env={}, workspace=_governance_ledger(tmp_path))
    assert verdict.ok
    assert verdict.reasons == ["governance_evolve_exempt"]


def test_governance_evolve_still_needs_a_bet_without_a_governance_bet(tmp_path: Path) -> None:
    verdict = BIND.start_requires_bet("governance-audit", "", env={}, workspace=_business_only_ledger(tmp_path))
    assert not verdict.ok
    assert verdict.reasons == ["missing_bet_id"]


def test_exemption_does_not_widen_to_ordinary_iterations(tmp_path: Path) -> None:
    workspace = _governance_ledger(tmp_path)
    for workflow in ("project-code-change", "project-doc-change", "bet-execution", "round-engineering"):
        verdict = BIND.start_requires_bet(workflow, "", env={}, workspace=workspace)
        assert not verdict.ok, f"{workflow} must still require a bet"
        assert verdict.reasons == ["missing_bet_id"]


def test_start_and_closeout_agree_on_the_exempt_set(tmp_path: Path) -> None:
    workspace = _governance_ledger(tmp_path)
    for workflow in sorted(BIND.GOVERNANCE_EVOLVE_WORKFLOWS):
        start = BIND.start_requires_bet(workflow, "", env={}, workspace=workspace)
        assert start.ok, f"{workflow} is exempt at closeout but not at start"
    assert BIND.start_requires_bet("observer-audit", "", env={}, workspace=workspace).ok
    # An exempt verdict must never be produced for a workflow carrying a bet it
    # cannot be bound to: a supplied bet id stays a plain pass, not an exemption.
    bound = BIND.start_requires_bet("governance-audit", "BET-Y2Q3-T7-01", env={}, workspace=workspace)
    assert bound.ok and bound.reasons == []
