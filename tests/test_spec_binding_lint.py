"""Canonical Specification Binding tests for the strategic BET ledger."""

from __future__ import annotations

import importlib.util
import sys
from argparse import Namespace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

_spec = importlib.util.spec_from_file_location("bet_ledger", ROOT / "bin/plan/bet-ledger.py")
assert _spec is not None and _spec.loader is not None
bl = importlib.util.module_from_spec(_spec)
sys.modules["bet_ledger"] = bl
_spec.loader.exec_module(bl)


def _bet(*, status: str = "candidate", risk_level: str = "L1") -> dict:
    return {
        "id": "BET-TEST",
        "risk_level": risk_level,
        "status": status,
        "track": "T1",
        "window": "Y1Q1",
        "title": "Canonical binding",
        "appetite": "1 day",
        "goal": "Prove one canonical binding",
        "done_when": ["binding is verified"],
        "verify": [{"cmd": "python3 -c pass", "expect": "exit 0"}],
        "workflow": "bet-execution",
        "write_surfaces": ["bin/agent-workflow.py", "tests/**"],
    }


def _write_spec(workspace: Path, content: str = "# Accepted specification\n") -> tuple[str, str]:
    relative = "docs/superpowers/specs/accepted.md"
    path = workspace / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return f"repo://{relative}", f"sha256:{bl._file_sha256(path)}"


def _canonical_binding(workspace: Path, bet_id: str = "BET-TEST") -> dict[str, str]:
    spec_ref, digest = _write_spec(workspace)
    return {
        "spec_ref": spec_ref,
        "spec_version": "1.0.0",
        "content_digest": digest,
        "decision_ref": f"decision://accepted/{bet_id}",
    }


def _lint_data(bet: dict) -> dict:
    return {
        "meta": {
            "status_enum": ["candidate", "pending", "in_progress", "review", "done", "blocked", "failed"],
            "windows": ["Y1Q1"],
        },
        "tracks": ["T1"],
        "bets": [bet],
    }


def test_candidate_requires_spec_without_date_or_risk_bypass() -> None:
    assert bl._is_spec_binding_required(_bet(risk_level="L1")) is True
    assert bl._is_spec_binding_required(_bet(risk_level="L3")) is True


def test_historical_terminal_bet_is_explicitly_grandfathered() -> None:
    historical = next(
        bet
        for bet in bl.load()["bets"]
        if bet["id"] == "BET-Y1Q2-T6-07"
    )

    assert bl._is_spec_binding_required(historical) is False
    assert bl._is_historical_spec_grandfathered(historical, workspace=ROOT) is True


def test_new_terminal_bet_cannot_self_grandfather_with_cutoff_date() -> None:
    newly_constructed = _bet(status="done", risk_level="L3")
    newly_constructed["done_at"] = bl.SPEC_BINDING_GRANDFATHER_CUTOFF

    assert bl._is_historical_spec_grandfathered(newly_constructed, workspace=ROOT) is False


def test_canonical_binding_validates(tmp_path: Path) -> None:
    bet = _bet()
    bet["accepted_specifications"] = [_canonical_binding(tmp_path)]

    binding, errors = bl.validate_accepted_specification(bet, workspace=tmp_path)

    assert errors == []
    assert binding == bet["accepted_specifications"][0]


def test_legacy_relative_ref_and_raw_digest_are_rejected(tmp_path: Path) -> None:
    bet = _bet()
    _spec_ref, digest = _write_spec(tmp_path)
    bet["accepted_specifications"] = [
        {
            "spec_ref": "accepted.md",
            "spec_version": "v1",
            "content_digest": digest.removeprefix("sha256:"),
            "decision_ref": "BET-TEST",
        }
    ]

    _binding, errors = bl.validate_accepted_specification(bet, workspace=tmp_path)

    assert any("spec_ref" in error and "repo://" in error for error in errors)
    assert any("spec_version" in error and "semver" in error for error in errors)
    assert any("content_digest" in error and "sha256:" in error for error in errors)
    assert any("decision_ref" in error and "decision://accepted/BET-TEST" in error for error in errors)


def test_digest_drift_is_rejected(tmp_path: Path) -> None:
    bet = _bet()
    binding = _canonical_binding(tmp_path)
    bet["accepted_specifications"] = [binding]
    (tmp_path / binding["spec_ref"].removeprefix("repo://")).write_text("changed", encoding="utf-8")

    _binding, errors = bl.validate_accepted_specification(bet, workspace=tmp_path)

    assert any("SPEC_DIGEST_MISMATCH" in error for error in errors)


def test_unaccepted_or_wrong_decision_status_is_rejected(tmp_path: Path) -> None:
    bet = _bet()
    binding = _canonical_binding(tmp_path)
    binding["decision_ref"] = "decision://proposed/BET-TEST"
    bet["accepted_specifications"] = [binding]

    _binding, errors = bl.validate_accepted_specification(bet, workspace=tmp_path)

    assert any("SPEC_DECISION_NOT_ACCEPTED" in error for error in errors)


def test_multiple_bindings_are_rejected_for_one_work_packet(tmp_path: Path) -> None:
    bet = _bet()
    binding = _canonical_binding(tmp_path)
    bet["accepted_specifications"] = [binding, dict(binding)]

    _binding, errors = bl.validate_accepted_specification(bet, workspace=tmp_path)

    assert any("exactly one" in error for error in errors)


def test_lint_fails_for_active_bet_without_binding(capsys) -> None:
    rc = bl.cmd_lint(_lint_data(_bet()), type("Args", (), {})())

    assert rc == 1
    assert "SPEC_BINDING_REQUIRED" in capsys.readouterr().out


def test_lint_rejects_newly_constructed_done_bet_without_binding(capsys) -> None:
    newly_constructed = _bet(status="done", risk_level="L3")
    newly_constructed["done_at"] = bl.SPEC_BINDING_GRANDFATHER_CUTOFF

    rc = bl.cmd_lint(_lint_data(newly_constructed), type("Args", (), {})())

    assert rc == 1
    assert "SPEC_BINDING_REQUIRED" in capsys.readouterr().out


def test_complete_rejects_unbound_nonterminal_bet_even_with_force(capsys) -> None:
    rc = bl.cmd_complete(
        _lint_data(_bet(status="candidate")),
        Namespace(bet_id="BET-TEST", force=True),
    )

    assert rc == 1
    assert "SPEC_BINDING_REQUIRED" in capsys.readouterr().out
