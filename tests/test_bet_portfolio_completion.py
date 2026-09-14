"""T1-06 Milestone/Vision derived completion gate fixtures."""

from __future__ import annotations

import copy
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]
MOD = ROOT / "bin" / "plan" / "chain_bind.py"
SPEC = importlib.util.spec_from_file_location("chain_bind", MOD)
assert SPEC and SPEC.loader
CB = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = CB
SPEC.loader.exec_module(CB)


def _ledger() -> dict:
    return {
        "vision": {"id": "VISION-2029"},
        "objectives": [
            {
                "id": "OBJ-TRUST",
                "key_results": [
                    {"id": "KR-TRUST-CHAIN-COVERAGE", "status": "proven"},
                    {"id": "KR-HOLDABILITY-ORPHAN-BETS", "status": "unmeasured"},
                ],
            }
        ],
        "campaigns": [{"id": "CMP-W0-PORTFOLIO-TRUTH"}],
        "milestones": [
            {
                "id": "MS-W0-CONTRACT",
                "required_bets": ["BET-A", "BET-B"],
                "required_krs": ["KR-TRUST-CHAIN-COVERAGE", "KR-HOLDABILITY-ORPHAN-BETS"],
            }
        ],
        "bets": [
            {"id": "BET-A", "status": "done"},
            {"id": "BET-B", "status": "done"},
            {"id": "BET-FAIL", "status": "failed", "replaced_by": "BET-REPL"},
            {"id": "BET-REPL", "status": "done", "replacement_of": "BET-FAIL"},
        ],
    }


def test_false_close_when_required_kr_unproven() -> None:
    ledger = _ledger()
    ms = ledger["milestones"][0]
    v = CB.evaluate_milestone(ms, ledger, {})
    assert v.ok is False
    assert v.code == "MILESTONE_FALSE_CLOSE"
    assert any("KR-HOLDABILITY-ORPHAN-BETS" in r for r in v.reasons)


def test_false_close_unresolved_blocker() -> None:
    ledger = _ledger()
    ledger["objectives"][0]["key_results"][1]["status"] = "proven"
    ms = ledger["milestones"][0]
    v = CB.evaluate_milestone(ms, ledger, {"unresolved_blocker": True})
    assert v.ok is False and v.code == "MILESTONE_FALSE_CLOSE"


def test_replacement_conserves_failed_leaf() -> None:
    ledger = _ledger()
    ledger["objectives"][0]["key_results"][1]["status"] = "proven"
    ms = {
        "id": "MS-X",
        "required_bets": ["BET-FAIL"],
        "required_krs": ["KR-TRUST-CHAIN-COVERAGE"],
    }
    v = CB.evaluate_milestone(ms, ledger, {})
    assert v.ok is True and v.code == "MILESTONE_MET"


def test_required_campaign_or_objective_unmet_blocks() -> None:
    ledger = _ledger()
    ledger["objectives"][0]["key_results"][1]["status"] = "proven"
    ms = ledger["milestones"][0]
    v = CB.evaluate_milestone(ms, ledger, {"required_campaigns_unmet": ["CMP-X"]})
    assert v.ok is False and "campaign unmet" in v.reasons[0]
    v2 = CB.evaluate_milestone(ms, ledger, {"required_objectives_unmet": ["OBJ-X"]})
    assert v2.ok is False and "objective unmet" in v2.reasons[0]


def test_value_exempt_cannot_advance_value_kr() -> None:
    vision = {"id": "VISION-2029"}
    window = [
        {"accepted_outputs": 5, "acceptance_rate": 0.9, "principal_bound": True, "partition": "real"}
        for _ in range(12)
    ]
    v = CB.evaluate_vision(
        vision,
        [{"ok": True, "code": "OBJ_MET"}],
        window,
        evidence={
            "human_final_verdict": True,
            "edit_burden_improved": True,
            "value_exempt_attempted_value_kr": True,
        },
    )
    assert v.ok is False and v.code == "VALUE_PROXY_REJECTED"


def test_eleven_week_window_fails_vision() -> None:
    vision = {"id": "VISION-2029"}
    window = [
        {"accepted_outputs": 5, "acceptance_rate": 0.9, "principal_bound": True, "partition": "real"}
        for _ in range(11)
    ]
    v = CB.evaluate_vision(
        vision,
        [{"ok": True, "code": "OBJ_MET"}],
        window,
        evidence={"human_final_verdict": True, "edit_burden_improved": True},
    )
    assert v.ok is False and v.code == "VISION_WINDOW_INCOMPLETE"


def test_synthetic_and_unbound_human_rejected() -> None:
    vision = {"id": "VISION-2029"}
    base = {"accepted_outputs": 5, "acceptance_rate": 0.9, "principal_bound": True, "partition": "real"}
    window = [copy.deepcopy(base) for _ in range(12)]
    window[0]["partition"] = "synthetic"
    v = CB.evaluate_vision(
        vision,
        [{"ok": True, "code": "OBJ_MET"}],
        window,
        evidence={"human_final_verdict": True, "edit_burden_improved": True},
    )
    assert v.ok is False and v.code == "VALUE_PROXY_REJECTED"

    window2 = [copy.deepcopy(base) for _ in range(12)]
    window2[0]["principal_bound"] = False
    v2 = CB.evaluate_vision(
        vision,
        [{"ok": True, "code": "OBJ_MET"}],
        window2,
        evidence={"human_final_verdict": True, "edit_burden_improved": True},
    )
    assert v2.ok is False and v2.code == "VALUE_PROXY_REJECTED"


def test_missing_human_final_verdict_fails() -> None:
    vision = {"id": "VISION-2029"}
    window = [
        {"accepted_outputs": 5, "acceptance_rate": 0.9, "principal_bound": True, "partition": "real"}
        for _ in range(12)
    ]
    v = CB.evaluate_vision(
        vision,
        [{"ok": True, "code": "OBJ_MET"}],
        window,
        evidence={"edit_burden_improved": True},
    )
    assert v.ok is False and v.code == "VISION_WINDOW_INCOMPLETE"


def test_valid_vision_and_milestone_pass_without_mutation() -> None:
    ledger = _ledger()
    ledger["objectives"][0]["key_results"][1]["status"] = "proven"
    before = copy.deepcopy(ledger)
    ms = ledger["milestones"][0]
    assert CB.evaluate_milestone(ms, ledger, {}).ok is True
    vision = ledger["vision"]
    window = [
        {"accepted_outputs": 5, "acceptance_rate": 0.9, "principal_bound": True, "partition": "real"}
        for _ in range(12)
    ]
    v = CB.evaluate_vision(
        vision,
        [{"ok": True, "code": "OBJ_MET"}],
        window,
        evidence={"human_final_verdict": True, "edit_burden_improved": True},
    )
    assert v.ok is True and v.code == "VISION_MET"
    assert ledger == before
