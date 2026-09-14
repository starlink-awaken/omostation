"""Regression guards for the retired merge-event dogfood collector."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "projects" / "omo" / "src"))

from omo.engineering_delivery_consumer import build_engineering_delivery_shadow_observer  # noqa: E402


def _load_bet_ledger():
    path = ROOT / "bin" / "plan" / "bet-ledger.py"
    spec = importlib.util.spec_from_file_location("_t7_truth_bet_ledger", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_t7_blocked_bet_is_not_claimable_by_an_agent() -> None:
    ledger = _load_bet_ledger()
    data = ledger.load()
    # Use a still-blocked BET (Y1Q2-T7-01 was completed via human approval on
    # 2026-08-22; the gate policy is exercised by Y3H1-T7-01 which carries the
    # same blocked_reentry_policy=human_approval_required).
    bet = ledger.bet_by_id(data, "BET-Y3H1-T7-01")

    claimable, reasons = ledger._claimable(data, bet)

    assert claimable is False
    assert any("agent 不得认领" in reason for reason in reasons)


def test_t7_blocked_bet_start_requires_audited_human_reentry() -> None:
    ledger = _load_bet_ledger()

    with pytest.raises(ledger.SpecBindingContractError, match="BET_BLOCKED_REENTRY_GATE"):
        ledger.prepare_bet_execution("BET-Y3H1-T7-01", workspace=ROOT)


def test_historical_merge_event_store_never_counts_as_qualified_outcome(tmp_path: Path) -> None:
    legacy_store = tmp_path / ".omo" / "_delivery" / "outcomes" / "dogfood-decision-outcomes.jsonl"
    legacy_store.parent.mkdir(parents=True)
    legacy_store.write_text(
        json.dumps(
            {
                "schema": "decision_outcome/v1",
                "namespace": "agent_belief",
                "scene_id": "engineering-delivery-dogfood",
                "decision_id": "do-dogfood-1858",
                "payload": {
                    "human_verdict": "accepted",
                    "verdict_source": "merge_event",
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )

    result = build_engineering_delivery_shadow_observer(
        tmp_path / ".omo",
        as_of="2026-08-19T12:16:45Z",
        query_only=True,
    )

    assert result["qualifying_decision_outcomes"] == 0
    assert result["verdict"] == "FAIL"
    assert result["human_gate"] == "not_ready"
    assert result["value_indicator_policy"] is False
