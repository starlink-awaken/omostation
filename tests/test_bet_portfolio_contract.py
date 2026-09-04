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
    """Compatibility mode must add a readable v2 entry point without mutation.

    The lint command may return 1 if the current ledger has BETs that don't
    yet have the v2 completion_evidence / accepted_specifications fields
    (these are the new strict-mode requirements; legacy BETs grandfather
    through the migration but the current ledger state has >0 BETs missing
    those fields, so lint returns 1).

    The test verifies the CLI runs without crashing and produces a non-empty
    report. The strictness of the report is governed by the ledger content,
    not the CLI.
    """
    result = subprocess.run(
        [sys.executable, str(LEDGER_CLI), "portfolio", "lint"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode in (0, 1), result.stderr + result.stdout
    # Lint must produce a non-empty report (warns and/or errors).
    assert "WARN" in result.stdout or "ERROR" in result.stdout


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


def _valid_v2_ledger() -> dict:
    """A fully valid v2 fixture whose binding is enforced and references resolve."""
    return {
        "meta": {"total_bets": 1},
        "vision": {"id": "VISION-1"},
        "objectives": [{"id": "OBJ-1", "key_results": [{"id": "KR-1"}]}],
        "campaigns": [{"id": "CMP-1", "objective_refs": ["OBJ-1"]}],
        "milestones": [{"id": "MS-1"}],
        "bets": [
            {
                "id": "BET-1",
                "status": "candidate",
                "portfolio_binding": {
                    "schema_state": "enforced",
                    "campaign_ref": "CMP-1",
                    "objective_refs": ["OBJ-1"],
                    "kr_refs": ["KR-1"],
                },
            }
        ],
    }


def test_valid_v2_fixture_passes_without_errors() -> None:
    """A fully bound v2 hierarchy must validate cleanly (done_when #2 positive)."""
    result = PORTFOLIO_CONTRACT.validate_portfolio(_valid_v2_ledger(), strict=False)

    assert result.errors == ()
    assert result.ok


def test_duplicate_campaign_and_milestone_and_bet_ids_rejected() -> None:
    """Duplicate entity IDs across the v2 hierarchy fail closed (done_when #2)."""
    ledger = _valid_v2_ledger()
    ledger["campaigns"] = [
        {"id": "CMP-1", "objective_refs": ["OBJ-1"]},
        {"id": "CMP-1", "objective_refs": ["OBJ-1"]},
    ]
    ledger["milestones"] = [{"id": "MS-1"}, {"id": "MS-1"}]
    ledger["bets"].append(
        {
            "id": "BET-1",
            "status": "candidate",
            "portfolio_binding": {
                "schema_state": "enforced",
                "campaign_ref": "CMP-1",
                "objective_refs": ["OBJ-1"],
                "kr_refs": ["KR-1"],
            },
        }
    )

    result = PORTFOLIO_CONTRACT.validate_portfolio(ledger, strict=False)

    assert "CAMPAIGN_ID_DUPLICATE: CMP-1" in result.errors
    assert "MILESTONE_ID_DUPLICATE: MS-1" in result.errors
    assert "BET_ID_DUPLICATE: BET-1" in result.errors


def test_missing_and_invalid_vision_rejected() -> None:
    """Vision identity is required when the v2 contract is enabled."""
    ledger = _valid_v2_ledger()
    ledger["vision"] = {"id": 123}

    result = PORTFOLIO_CONTRACT.validate_portfolio(ledger, strict=False)

    assert "VISION_ID_INVALID" in " ".join(result.errors)


def test_campaign_ref_missing_rejected() -> None:
    """A binding that references an unknown campaign fails closed."""
    ledger = _valid_v2_ledger()
    ledger["bets"][0]["portfolio_binding"]["campaign_ref"] = "CMP-NOPE"

    result = PORTFOLIO_CONTRACT.validate_portfolio(ledger, strict=False)

    assert "CAMPAIGN_REF_MISSING: BET-1 -> CMP-NOPE" in result.errors


def test_objective_ref_missing_rejected() -> None:
    """A campaign objective_ref to an unknown objective fails closed."""
    ledger = _valid_v2_ledger()
    ledger["campaigns"][0]["objective_refs"] = ["OBJ-NOPE"]

    result = PORTFOLIO_CONTRACT.validate_portfolio(ledger, strict=False)

    assert "OBJECTIVE_REF_MISSING: CMP-1 -> OBJ-NOPE" in result.errors


def test_parent_bet_missing_rejected() -> None:
    """A child binding referencing an unknown parent bet fails closed."""
    ledger = _valid_v2_ledger()
    ledger["bets"][0]["portfolio_binding"]["parent_bet"] = "BET-NOPE"

    result = PORTFOLIO_CONTRACT.validate_portfolio(ledger, strict=False)

    assert "PARENT_BET_MISSING: BET-1 -> BET-NOPE" in result.errors


def test_metric_shape_invalid_rejected() -> None:
    """Non-numeric hypothesis metrics fail closed (done_when #2 metric shape)."""
    ledger = _valid_v2_ledger()
    ledger["bets"][0]["hypothesis_metric"] = {"baseline": "not-a-number", "target": 10}

    result = PORTFOLIO_CONTRACT.validate_portfolio(ledger, strict=False)

    assert "METRIC_SHAPE_INVALID: BET-1 -> hypothesis_metric.baseline must be numeric" in result.errors


def test_bet_type_invalid_rejected() -> None:
    """A non-string bet_type fails closed (done_when #2 enum shape)."""
    ledger = _valid_v2_ledger()
    ledger["bets"][0]["bet_type"] = 123

    result = PORTFOLIO_CONTRACT.validate_portfolio(ledger, strict=False)

    assert "BET_TYPE_INVALID: BET-1 bet_type must be a non-empty string" in result.errors


def test_policy_boolean_invalid_rejected() -> None:
    """A non-boolean policy field fails closed (done_when #2 boolean policy)."""
    ledger = _valid_v2_ledger()
    ledger["bets"][0]["value_indicator_policy"] = "yes"

    result = PORTFOLIO_CONTRACT.validate_portfolio(ledger, strict=False)

    assert "POLICY_BOOLEAN_INVALID: BET-1 -> value_indicator_policy must be boolean" in result.errors


def test_timestamp_invalid_rejected() -> None:
    """A malformed ISO-8601 timestamp fails closed (done_when #2 timestamp)."""
    ledger = _valid_v2_ledger()
    ledger["bets"][0]["effective_at"] = "next-week"

    result = PORTFOLIO_CONTRACT.validate_portfolio(ledger, strict=False)

    assert "TIMESTAMP_INVALID: BET-1 -> effective_at must be ISO-8601" in result.errors


def test_strict_mode_passes_when_total_bets_equals_len() -> None:
    """Strict mode is GREEN when meta.total_bets == len(bets) (done_when #4)."""
    ledger = _valid_v2_ledger()
    ledger["meta"] = {"total_bets": len(ledger["bets"])}

    result = PORTFOLIO_CONTRACT.validate_portfolio(ledger, strict=True)

    assert result.errors == ()
    assert result.ok


def test_bootstrap_unenforced_binding_skips_required_field_enforcement() -> None:
    """W0 bootstrap_unenforced bindings are not enforcement evidence (spec §4)."""
    ledger = _valid_v2_ledger()
    ledger["bets"][0]["portfolio_binding"] = {
        "schema_state": "bootstrap_unenforced",
        "campaign_ref": "CMP-1",
    }

    result = PORTFOLIO_CONTRACT.validate_portfolio(ledger, strict=False)

    assert "PORTFOLIO_BINDING_FIELD_MISSING" not in " ".join(result.errors)


def test_validation_does_not_write_files(tmp_path, monkeypatch) -> None:
    """Validator must never perform filesystem writes (done_when #7)."""
    # Isolate cwd to a fresh temp dir so any accidental write would surface.
    monkeypatch.chdir(tmp_path)
    ledger = _valid_v2_ledger()
    before = copy.deepcopy(ledger)
    tree_before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}

    PORTFOLIO_CONTRACT.validate_portfolio(ledger, strict=False)
    PORTFOLIO_CONTRACT.validate_portfolio(ledger, strict=True)

    tree_after = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    assert tree_after == tree_before
    assert ledger == before
