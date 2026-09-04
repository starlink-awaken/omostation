"""T1-04 Portfolio v2 compatibility contract tests."""

from __future__ import annotations

import copy
import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]
LEDGER_CLI = ROOT / "bin" / "plan" / "bet-ledger.py"
CONTRACT_PATH = ROOT / "bin" / "plan" / "portfolio_contract.py"
SPEC = importlib.util.spec_from_file_location("portfolio_contract", CONTRACT_PATH)
assert SPEC and SPEC.loader
PORTFOLIO_CONTRACT = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = PORTFOLIO_CONTRACT
SPEC.loader.exec_module(PORTFOLIO_CONTRACT)


def test_portfolio_lint_accepts_the_current_legacy_ledger() -> None:
    """Compatibility mode must add a readable v2 entry point without mutation."""
    result = subprocess.run(
        [sys.executable, str(LEDGER_CLI), "portfolio", "lint"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr + result.stdout


def test_validator_rejects_duplicate_v2_entity_ids_without_mutating_input() -> None:
    ledger = {
        "vision": {"id": "VISION-TEST"},
        "objectives": [
            {"id": "OBJ-DUP", "key_results": []},
            {"id": "OBJ-DUP", "key_results": []},
        ],
        "campaigns": [],
        "milestones": [],
        "bets": [],
    }
    before = copy.deepcopy(ledger)

    result = PORTFOLIO_CONTRACT.validate_portfolio(ledger, strict=False)

    assert "OBJECTIVE_ID_DUPLICATE: OBJ-DUP" in result.errors
    assert ledger == before


def test_total_bets_drift_warns_in_compatibility_and_fails_in_strict_mode() -> None:
    ledger = {"meta": {"total_bets": 1}, "bets": []}

    compatibility = PORTFOLIO_CONTRACT.validate_portfolio(ledger, strict=False)
    strict = PORTFOLIO_CONTRACT.validate_portfolio(ledger, strict=True)

    assert compatibility.errors == ()
    assert compatibility.warnings == ("META_TOTAL_BETS_DRIFT: declared=1 actual=0",)
    assert strict.errors == ("META_TOTAL_BETS_DRIFT: declared=1 actual=0",)


def test_validator_rejects_a_v2_bet_with_a_missing_key_result_reference() -> None:
    ledger = {
        "meta": {"total_bets": 1},
        "vision": {"id": "VISION-TEST", "required_objectives": ["OBJ-TEST"]},
        "objectives": [{"id": "OBJ-TEST", "key_results": [{"id": "KR-REAL"}]}],
        "campaigns": [{"id": "CMP-TEST", "objective_refs": ["OBJ-TEST"]}],
        "milestones": [],
        "bets": [
            {
                "id": "BET-TEST",
                "portfolio_binding": {
                    "campaign_ref": "CMP-TEST",
                    "objective_refs": ["OBJ-TEST"],
                    "kr_refs": ["KR-MISSING"],
                },
            }
        ],
    }

    result = PORTFOLIO_CONTRACT.validate_portfolio(ledger, strict=False)

    assert "KR_REF_MISSING: BET-TEST -> KR-MISSING" in result.errors


def test_validator_requires_portfolio_binding_fields_for_a_nonterminal_v2_bet() -> None:
    ledger = {
        "meta": {"total_bets": 1},
        "vision": {"id": "VISION-TEST"},
        "objectives": [],
        "campaigns": [],
        "milestones": [],
        "bets": [{"id": "BET-TEST", "status": "candidate", "portfolio_binding": {}}],
    }

    result = PORTFOLIO_CONTRACT.validate_portfolio(ledger, strict=False)

    assert "PORTFOLIO_BINDING_FIELD_MISSING: BET-TEST -> campaign_ref" in result.errors
    assert "PORTFOLIO_BINDING_FIELD_MISSING: BET-TEST -> objective_refs" in result.errors
    assert "PORTFOLIO_BINDING_FIELD_MISSING: BET-TEST -> kr_refs" in result.errors
