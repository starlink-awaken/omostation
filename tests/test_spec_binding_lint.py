"""Canonical Specification Binding tests for the strategic BET ledger."""

from __future__ import annotations

import base64
import importlib.util
import json
import os
import subprocess
import sys
from argparse import Namespace
from pathlib import Path
from typing import Any

import pytest
import yaml

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


def _accepted_spec_content(
    *,
    status: str = "accepted",
    spec_version: str = "1.0.0",
    bet_id: str = "BET-TEST",
) -> str:
    return (
        "---\n"
        "schema_version: specification/v1\n"
        f"spec_version: {spec_version}\n"
        f"status: {status}\n"
        f"bet_id: {bet_id}\n"
        "---\n\n"
        "# Canonical specification\n"
    )


def _write_spec(workspace: Path, content: str | None = None) -> tuple[str, str]:
    relative = "docs/superpowers/specs/accepted.md"
    path = workspace / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content or _accepted_spec_content(), encoding="utf-8")
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
    # Candidate BETs are intentionally parked placeholders — they cannot be
    # dispatched and have no accepted spec.  Skip binding enforcement so
    # parked candidates do not create permanent CI red.
    assert bl._is_spec_binding_required(_bet(risk_level="L1")) is False
    assert bl._is_spec_binding_required(_bet(risk_level="L3")) is False


def test_historical_terminal_bet_is_explicitly_grandfathered() -> None:
    historical = next(
        bet
        for bet in bl.load()["bets"]
        if bet["id"] == "BET-Y1Q2-T6-07"
    )

    assert bl._is_spec_binding_required(historical) is False
    assert bl._is_historical_spec_grandfathered(historical, workspace=ROOT) is True


def test_pre_v1_spec_frontmatter_is_grandfathered_only_by_exact_binding() -> None:
    historical = next(bet for bet in bl.load()["bets"] if bet["id"] == "BET-Y1Q2-T1-19")
    binding = historical["accepted_specifications"][0]

    assert bl._is_spec_frontmatter_grandfathered(historical, binding) is True
    assert bl._is_spec_frontmatter_grandfathered(
        historical,
        {**binding, "content_digest": "sha256:" + "0" * 64},
    ) is False


def test_pre_v1_t1_19_binding_passes_end_to_end_validator() -> None:
    historical = next(bet for bet in bl.load()["bets"] if bet["id"] == "BET-Y1Q2-T1-19")

    binding, errors = bl.validate_accepted_specification(historical, workspace=ROOT)

    assert errors == []
    assert binding == historical["accepted_specifications"][0]


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


@pytest.mark.parametrize("status", ["draft", "superseded"])
def test_binding_rejects_spec_that_is_not_accepted(tmp_path: Path, status: str) -> None:
    bet = _bet()
    bet["accepted_specifications"] = [
        _canonical_binding(tmp_path)
    ]
    spec_path = tmp_path / bet["accepted_specifications"][0]["spec_ref"].removeprefix("repo://")
    spec_path.write_text(_accepted_spec_content(status=status), encoding="utf-8")
    bet["accepted_specifications"][0]["content_digest"] = f"sha256:{bl._file_sha256(spec_path)}"

    _binding, errors = bl.validate_accepted_specification(bet, workspace=tmp_path)

    assert any("SPEC_STATUS_NOT_ACCEPTED" in error for error in errors)


def test_binding_rejects_frontmatter_version_or_bet_mismatch(tmp_path: Path) -> None:
    bet = _bet()
    bet["accepted_specifications"] = [_canonical_binding(tmp_path)]
    spec_path = tmp_path / bet["accepted_specifications"][0]["spec_ref"].removeprefix("repo://")
    spec_path.write_text(
        _accepted_spec_content(spec_version="2.0.0", bet_id="BET-OTHER"),
        encoding="utf-8",
    )
    bet["accepted_specifications"][0]["content_digest"] = f"sha256:{bl._file_sha256(spec_path)}"

    _binding, errors = bl.validate_accepted_specification(bet, workspace=tmp_path)

    assert any("SPEC_FRONTMATTER_VERSION_MISMATCH" in error for error in errors)
    assert any("SPEC_FRONTMATTER_BET_MISMATCH" in error for error in errors)


def test_binding_rejects_missing_canonical_frontmatter(tmp_path: Path) -> None:
    bet = _bet()
    spec_ref, digest = _write_spec(tmp_path, "# No frontmatter\n")
    bet["accepted_specifications"] = [
        {
            "spec_ref": spec_ref,
            "spec_version": "1.0.0",
            "content_digest": digest,
            "decision_ref": "decision://accepted/BET-TEST",
        }
    ]

    _binding, errors = bl.validate_accepted_specification(bet, workspace=tmp_path)

    assert any("SPEC_FRONTMATTER_INVALID" in error for error in errors)


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
    rc = bl.cmd_lint(_lint_data(_bet(status="pending")), type("Args", (), {})())

    assert rc == 1
    assert "SPEC_BINDING_REQUIRED" in capsys.readouterr().out


def test_lint_allows_done_bet_without_binding_grandfathered(
    monkeypatch: pytest.MonkeyPatch,
    capsys,
) -> None:
    """#3209 契约: done 无 binding 在 lint 层安静 (validate_accepted_specification
    对 done 返回空错误) — 准入约束由 cmd_complete + workflow start 门承担,
    lint 只管 transition-diff (done_at/matrix 状态一致性)。"""
    newly_constructed = _bet(status="done", risk_level="L3")
    newly_constructed["done_at"] = bl.SPEC_BINDING_GRANDFATHER_CUTOFF
    # 注入 base (BET 不存在 = 新 done 转移): 即使构成转移, 无 binding 仍安静
    _transition_base(monkeypatch, base_status=None)

    rc = bl.cmd_lint(_lint_data(newly_constructed), type("Args", (), {})())

    out = capsys.readouterr().out
    assert rc == 0
    assert "SPEC_BINDING_REQUIRED" not in out


def test_complete_rejects_unbound_nonterminal_bet_even_with_force(capsys) -> None:
    rc = bl.cmd_complete(
        _lint_data(_bet(status="pending")),
        Namespace(bet_id="BET-TEST", force=True),
    )

    assert rc == 1
    assert "SPEC_BINDING_REQUIRED" in capsys.readouterr().out


def _completion_matrix(
    *,
    engineering: str,
    operational: str,
    value: str,
    overall_state: str,
    evidence: dict[str, dict] | None = None,
) -> dict:
    evidence = evidence or {"engineering": {}, "operational": {}, "value": {}}
    return {
        "schema_version": "completion-evidence-matrix/v1",
        "axes": {
            "engineering": {
                "status": engineering,
                "evidence": evidence["engineering"],
            },
            "operational": {
                "status": operational,
                "evidence": evidence["operational"],
            },
            "value": {
                "status": value,
                "evidence": evidence["value"],
            },
        },
        "overall_state": overall_state,
    }


def _direct_evidence(workspace: Path) -> dict[str, dict]:
    subprocess.run(["git", "init", "-q", str(workspace)], check=True)
    subprocess.run(["git", "-C", str(workspace), "config", "user.email", "tests@example.invalid"], check=True)
    subprocess.run(["git", "-C", str(workspace), "config", "user.name", "Tests"], check=True)
    seed = workspace / "seed.txt"
    seed.write_text("seed\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(workspace), "add", "seed.txt"], check=True)
    subprocess.run(["git", "-C", str(workspace), "commit", "-qm", "seed"], check=True)
    commit = subprocess.run(
        ["git", "-C", str(workspace), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    subprocess.run(
        ["git", "-C", str(workspace), "update-ref", "refs/remotes/origin/main", commit],
        check=True,
    )

    result: dict[str, dict] = {
        "engineering": {"merged_reachable_commit": {"ref": f"git://origin/main@{commit}"}},
        "operational": {},
        "value": {},
    }
    file_keys = {
        "engineering": ("tests", "diff", "rollback"),
        "operational": ("live_canary", "fresh_receipt", "replay", "cleanup"),
    }
    for axis, keys in file_keys.items():
        for key in keys:
            relative = f"evidence/{axis}-{key}.json"
            path = workspace / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f'{{"kind":"{key}"}}\n', encoding="utf-8")
            result[axis][key] = {
                "ref": f"receipt://{relative}",
                "sha256": f"sha256:{bl._file_sha256(path)}",
            }

    result["value"] = {
        key: {"untrusted": "self-asserted"}
        for key in ("real_signal", "human_verdict", "revision", "time_burden")
    }
    return result


def test_value_exempt_verified_delivery_derives_delivery_accepted(tmp_path: Path) -> None:
    matrix = _completion_matrix(
        engineering="VERIFIED",
        operational="PROVEN",
        value="NOT_PROVEN",
        overall_state="delivery_accepted",
        evidence=_direct_evidence(tmp_path),
    )

    state, errors = bl.validate_completion_evidence(
        matrix,
        value_indicator_policy=False,
        workspace=tmp_path,
    )

    assert state == "delivery_accepted"
    assert errors == []


def test_value_exempt_bet_rejects_accepted_value(tmp_path: Path) -> None:
    matrix = _completion_matrix(
        engineering="VERIFIED",
        operational="PROVEN",
        value="ACCEPTED",
        overall_state="blocked",
        evidence=_direct_evidence(tmp_path),
    )

    state, errors = bl.validate_completion_evidence(
        matrix,
        value_indicator_policy=False,
        workspace=tmp_path,
    )

    assert state == "blocked"
    assert any("COMPLETION_VALUE_POLICY_VIOLATION" in error for error in errors)


def test_unspecified_value_policy_keeps_outcome_required(tmp_path: Path) -> None:
    matrix = _completion_matrix(
        engineering="VERIFIED",
        operational="PROVEN",
        value="NOT_PROVEN",
        overall_state="blocked",
        evidence=_direct_evidence(tmp_path),
    )

    state, errors = bl.validate_completion_evidence(matrix, workspace=tmp_path)

    assert state == "blocked"
    assert errors == []


def test_engineering_only_never_derives_outcome_accepted(tmp_path: Path) -> None:
    evidence = _direct_evidence(tmp_path)
    matrix = _completion_matrix(
        engineering="VERIFIED",
        operational="NOT_PROVEN",
        value="NOT_PROVEN",
        overall_state="blocked",
        evidence=evidence,
    )

    state, errors = bl.validate_completion_evidence(matrix, workspace=tmp_path)

    assert errors == []
    assert state == "blocked"


def test_self_asserted_value_evidence_cannot_make_outcome_accepted(tmp_path: Path) -> None:
    evidence = _direct_evidence(tmp_path)
    matrix = _completion_matrix(
        engineering="VERIFIED",
        operational="PROVEN",
        value="ACCEPTED",
        overall_state="outcome_accepted",
        evidence=evidence,
    )

    state, errors = bl.validate_completion_evidence(matrix, workspace=tmp_path)

    assert state == "blocked"
    assert any("COMPLETION_HUMAN_AUTH_REQUIRED" in error for error in errors)


def test_value_acceptance_without_human_verdict_fails_closed(tmp_path: Path) -> None:
    evidence = _direct_evidence(tmp_path)
    matrix = _completion_matrix(
        engineering="VERIFIED",
        operational="PROVEN",
        value="ACCEPTED",
        overall_state="outcome_accepted",
        evidence=evidence,
    )
    del matrix["axes"]["value"]["evidence"]["human_verdict"]

    state, errors = bl.validate_completion_evidence(matrix, workspace=tmp_path)

    assert state == "blocked"
    assert any("human_verdict" in error for error in errors)


def test_declared_overall_state_cannot_override_measured_axes(tmp_path: Path) -> None:
    evidence = _direct_evidence(tmp_path)
    matrix = _completion_matrix(
        engineering="VERIFIED",
        operational="DEGRADED",
        value="NOT_PROVEN",
        overall_state="outcome_accepted",
        evidence=evidence,
    )

    state, errors = bl.validate_completion_evidence(matrix, workspace=tmp_path)

    assert state == "blocked"
    assert any("OVERALL_STATE_MISMATCH" in error for error in errors)


def test_lint_rejects_declared_completion_matrix_that_is_not_measured(capsys) -> None:
    bet = _bet(status="done")
    bet["completion_evidence"] = _completion_matrix(
        engineering="IN_PROGRESS",
        operational="DEGRADED",
        value="NOT_PROVEN",
        overall_state="outcome_accepted",
    )

    rc = bl.cmd_lint(_lint_data(bet), type("Args", (), {})())

    assert rc == 1
    assert "OVERALL_STATE_MISMATCH" in capsys.readouterr().out


def test_lint_requires_matrix_for_in_progress_bet(capsys) -> None:
    bet = _bet(status="in_progress")

    rc = bl.cmd_lint(_lint_data(bet), type("Args", (), {})())

    assert rc == 1
    assert "COMPLETION_EVIDENCE_REQUIRED" in capsys.readouterr().out


def test_lint_allows_done_bet_without_matrix_grandfathered(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys,
) -> None:
    """#3209 契约: done 无 completion_evidence 在 lint 层安静 (cmd_lint 的
    COMPLETION_EVIDENCE_REQUIRED 只对非 done 的 matrix-required 状态生效) —
    done 证据闸在 cmd_complete; lint 的 transition 守卫只校验已有 matrix 的
    状态一致性 (BET_DONE_REQUIRES_*) 与 done_at 存在性。"""
    bet = _bet(status="done")
    bet["done_at"] = "2026-08-21"
    bet["accepted_specifications"] = [_canonical_binding(tmp_path)]
    monkeypatch.setattr(bl, "WS", tmp_path)
    # 注入 base (BET 不存在 = 新 done 转移): 即使构成转移, 无 matrix 仍安静
    _transition_base(monkeypatch, base_status=None)

    rc = bl.cmd_lint(_lint_data(bet), type("Args", (), {})())

    out = capsys.readouterr().out
    assert rc == 0
    assert "COMPLETION_EVIDENCE_REQUIRED" not in out


def _transition_base(monkeypatch: pytest.MonkeyPatch, *, base_status: str | None) -> None:
    """Inject a resolved base ledger so cmd_lint can classify done transitions.

    ``base_status`` is the BET-TEST status in the base revision; ``None`` means
    the BET does not exist in the base at all (a newly added done BET is a
    transition too).
    """
    monkeypatch.setenv("BET_LEDGER_BASE_REF", "HEAD")
    base: dict[str, str] = {}
    if base_status is not None:
        base["BET-TEST"] = base_status
    monkeypatch.setattr(
        bl,
        "_ledger_base_statuses",
        lambda ref, *, workspace: dict(base),
    )


def test_lint_rejects_transitioned_done_bet_whose_matrix_derives_evaluating(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys,
) -> None:
    bet = _bet(status="done")
    bet["done_at"] = "2026-08-25"
    bet["accepted_specifications"] = [_canonical_binding(tmp_path)]
    bet["completion_evidence"] = _completion_matrix(
        engineering="IN_PROGRESS",
        operational="NOT_PROVEN",
        value="NOT_PROVEN",
        overall_state="evaluating",
    )
    monkeypatch.setattr(bl, "WS", tmp_path)
    _transition_base(monkeypatch, base_status="candidate")

    rc = bl.cmd_lint(_lint_data(bet), type("Args", (), {})())

    assert rc == 1
    assert "BET_DONE_REQUIRES_OUTCOME_ACCEPTED" in capsys.readouterr().out


def test_lint_requires_done_at_for_transitioned_done_bet_with_outcome_accepted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys,
) -> None:
    bet = _bet(status="done")
    bet["accepted_specifications"] = [_canonical_binding(tmp_path)]
    bet["completion_evidence"] = _completion_matrix(
        engineering="VERIFIED",
        operational="PROVEN",
        value="ACCEPTED",
        overall_state="outcome_accepted",
    )
    monkeypatch.setattr(bl, "WS", tmp_path)
    _transition_base(monkeypatch, base_status="candidate")
    monkeypatch.setattr(
        bl,
        "validate_completion_evidence",
        lambda matrix, *, value_indicator_policy=True, workspace, done_at=None, bet_status=None: ("outcome_accepted", []),
    )

    rc = bl.cmd_lint(_lint_data(bet), type("Args", (), {})())

    assert rc == 1
    assert "BET_DONE_AT_REQUIRED" in capsys.readouterr().out


def test_lint_accepts_transitioned_done_bet_with_outcome_accepted_and_done_at(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys,
) -> None:
    bet = _bet(status="done")
    bet["done_at"] = "2026-08-25"
    bet["accepted_specifications"] = [_canonical_binding(tmp_path)]
    bet["completion_evidence"] = _completion_matrix(
        engineering="VERIFIED",
        operational="PROVEN",
        value="ACCEPTED",
        overall_state="outcome_accepted",
    )
    monkeypatch.setattr(bl, "WS", tmp_path)
    _transition_base(monkeypatch, base_status="candidate")
    monkeypatch.setattr(
        bl,
        "validate_completion_evidence",
        lambda matrix, *, value_indicator_policy=True, workspace, done_at=None, bet_status=None: ("outcome_accepted", []),
    )

    rc = bl.cmd_lint(_lint_data(bet), type("Args", (), {})())

    assert rc == 0


def test_lint_accepts_value_exempt_done_transition(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bet = _bet(status="done")
    bet["done_at"] = "2026-08-28"
    bet["value_indicator_policy"] = False
    bet["accepted_specifications"] = [_canonical_binding(tmp_path)]
    bet["completion_evidence"] = _completion_matrix(
        engineering="VERIFIED",
        operational="PROVEN",
        value="NOT_PROVEN",
        overall_state="delivery_accepted",
        evidence=_direct_evidence(tmp_path),
    )
    monkeypatch.setattr(bl, "WS", tmp_path)
    _transition_base(monkeypatch, base_status="candidate")

    assert bl.cmd_lint(_lint_data(bet), type("Args", (), {})()) == 0


@pytest.mark.parametrize("policy", ["false", 0, None, []], ids=["string", "number", "null", "list"])
def test_lint_rejects_non_boolean_value_indicator_policy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys,
    policy: object,
) -> None:
    bet = _bet()
    bet["value_indicator_policy"] = policy
    bet["accepted_specifications"] = [_canonical_binding(tmp_path)]
    monkeypatch.setattr(bl, "WS", tmp_path)

    assert bl.cmd_lint(_lint_data(bet), type("Args", (), {})()) == 1
    assert (
        "ERROR BET-TEST.value_indicator_policy: "
        "VALUE_INDICATOR_POLICY_TYPE: value_indicator_policy must be a boolean"
    ) in capsys.readouterr().out


def test_lint_unchanged_done_bet_keeps_baseline_without_done_findings(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys,
) -> None:
    """Historical done BET with an internally-valid evaluating matrix is baseline-clean."""
    bet = _bet(status="done")
    bet["done_at"] = "2026-08-24"
    bet["accepted_specifications"] = [_canonical_binding(tmp_path)]
    bet["completion_evidence"] = _completion_matrix(
        engineering="IN_PROGRESS",
        operational="NOT_PROVEN",
        value="NOT_PROVEN",
        overall_state="evaluating",
    )
    monkeypatch.setattr(bl, "WS", tmp_path)
    _transition_base(monkeypatch, base_status="done")

    rc = bl.cmd_lint(_lint_data(bet), type("Args", (), {})())

    out = capsys.readouterr().out
    assert rc == 0
    assert "BET_DONE_REQUIRES_OUTCOME_ACCEPTED" not in out
    assert "BET_DONE_AT_REQUIRED" not in out


def test_lint_new_bet_marked_done_counts_as_transition(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys,
) -> None:
    """A BET absent from the base has no done baseline, so done is a transition."""
    bet = _bet(status="done")
    bet["done_at"] = "2026-08-25"
    bet["accepted_specifications"] = [_canonical_binding(tmp_path)]
    bet["completion_evidence"] = _completion_matrix(
        engineering="IN_PROGRESS",
        operational="NOT_PROVEN",
        value="NOT_PROVEN",
        overall_state="evaluating",
    )
    monkeypatch.setattr(bl, "WS", tmp_path)
    _transition_base(monkeypatch, base_status=None)

    rc = bl.cmd_lint(_lint_data(bet), type("Args", (), {})())

    assert rc == 1
    assert "BET_DONE_REQUIRES_OUTCOME_ACCEPTED" in capsys.readouterr().out


def test_lint_without_resolved_base_produces_no_done_findings(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys,
) -> None:
    """Clean checkout / undetectable ledger transition keeps the guard off."""
    bet = _bet(status="done")
    bet["done_at"] = "2026-08-24"
    bet["accepted_specifications"] = [_canonical_binding(tmp_path)]
    bet["completion_evidence"] = _completion_matrix(
        engineering="IN_PROGRESS",
        operational="NOT_PROVEN",
        value="NOT_PROVEN",
        overall_state="evaluating",
    )
    monkeypatch.setattr(bl, "WS", tmp_path)
    monkeypatch.delenv("BET_LEDGER_BASE_REF", raising=False)
    monkeypatch.delenv("GITHUB_EVENT_PATH", raising=False)

    rc = bl.cmd_lint(_lint_data(bet), type("Args", (), {})())

    out = capsys.readouterr().out
    assert rc == 0
    assert "BET_DONE_" not in out


def test_lint_fails_closed_when_declared_base_is_unreadable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys,
) -> None:
    """A declared-but-unreadable base fails lint without inventing BET_DONE_ findings."""
    bet = _bet(status="done")
    bet["done_at"] = "2026-08-25"
    bet["accepted_specifications"] = [_canonical_binding(tmp_path)]
    bet["completion_evidence"] = _completion_matrix(
        engineering="VERIFIED",
        operational="PROVEN",
        value="ACCEPTED",
        overall_state="outcome_accepted",
    )
    monkeypatch.setattr(bl, "WS", tmp_path)
    monkeypatch.setenv("BET_LEDGER_BASE_REF", "deadbeef")
    monkeypatch.setattr(
        bl,
        "validate_completion_evidence",
        lambda matrix, *, value_indicator_policy=True, workspace, done_at=None, bet_status=None: ("outcome_accepted", []),
    )

    rc = bl.cmd_lint(_lint_data(bet), type("Args", (), {})())

    out = capsys.readouterr().out
    assert rc == 1
    assert "BASE_LEDGER_UNREADABLE" in out
    assert "BET_DONE_" not in out


def _base_ref_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "tests@example.invalid"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "Tests"], check=True)
    ledger = repo / "docs" / "plans" / "3y-bet-ledger.yaml"
    ledger.parent.mkdir(parents=True, exist_ok=True)
    ledger.write_text(
        "meta: {}\nbets:\n- id: BET-A\n  status: candidate\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "-C", str(repo), "add", "docs/plans/3y-bet-ledger.yaml"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "seed ledger"], check=True)
    return repo


def test_base_ref_resolver_prefers_explicit_override(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BET_LEDGER_BASE_REF", "refs/heads/baseline")
    monkeypatch.delenv("GITHUB_EVENT_PATH", raising=False)

    assert bl._resolve_ledger_base_ref(workspace=tmp_path) == "refs/heads/baseline"


def test_base_ref_resolver_reads_github_event_payload(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("BET_LEDGER_BASE_REF", raising=False)
    sha = "b" * 40
    event_path = tmp_path / "event.json"
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event_path))

    event_path.write_text(
        json.dumps({"pull_request": {"base": {"sha": sha}}}),
        encoding="utf-8",
    )
    assert bl._resolve_ledger_base_ref(workspace=tmp_path) == sha

    event_path.write_text(json.dumps({"before": sha}), encoding="utf-8")
    assert bl._resolve_ledger_base_ref(workspace=tmp_path) == sha

    # An all-zero push "before" (new-branch push) is not a usable base; with no
    # local ledger change either, the resolver must yield None.
    event_path.write_text(json.dumps({"before": "0" * 40}), encoding="utf-8")
    assert bl._resolve_ledger_base_ref(workspace=tmp_path) is None


def test_base_ref_resolver_compares_local_ledger_against_head(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("BET_LEDGER_BASE_REF", raising=False)
    monkeypatch.delenv("GITHUB_EVENT_PATH", raising=False)
    repo = _base_ref_repo(tmp_path)

    assert bl._resolve_ledger_base_ref(workspace=repo) is None

    ledger = repo / "docs" / "plans" / "3y-bet-ledger.yaml"
    ledger.write_text(
        "meta: {}\nbets:\n- id: BET-A\n  status: done\n",
        encoding="utf-8",
    )
    assert bl._resolve_ledger_base_ref(workspace=repo) == "HEAD"


def test_real_ledger_lint_adds_zero_done_findings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The repository ledger under a clean base comparison adds no BET_DONE_ lines."""
    monkeypatch.delenv("BET_LEDGER_BASE_REF", raising=False)
    monkeypatch.delenv("GITHUB_EVENT_PATH", raising=False)
    result = subprocess.run(
        [sys.executable, str(ROOT / "bin/plan/bet-ledger.py"), "lint"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    combined = result.stdout + result.stderr

    assert "BET_DONE_" not in combined
    assert "BASE_LEDGER_UNREADABLE" not in combined


GOVERNANCE_WORKFLOW = ROOT / ".github/workflows/governance-check.yml"
BET_GATE_WORKFLOW = ROOT / ".github/workflows/bet-done-gate.yml"
BET_GATE_JOB_ID = "bet-done-transition"
BET_GATE_STEP_NAME = "BET done-transition gate"
POINTER_DRIFT_STEP_NAME = "Submodule pointer drift check"
POINTER_STRICT_STEP_NAME = "Submodule pointer strict auto-bump gate"


def _governance_workflow() -> dict:
    return yaml.safe_load(GOVERNANCE_WORKFLOW.read_text(encoding="utf-8"))


def _governance_verify_steps() -> list[dict]:
    return _governance_workflow()["jobs"]["governance-verify"]["steps"]


def _bet_gate_jobs() -> dict:
    """bet-done gate 的 job 表 — 2026-08-26 起该 job 住在独立必跑 workflow
    (bet-done-gate.yml, 根治 #2197 悬空 required check); 兼容回退旧位置。"""
    if BET_GATE_WORKFLOW.exists():
        return yaml.safe_load(BET_GATE_WORKFLOW.read_text(encoding="utf-8"))["jobs"]
    return _governance_workflow()["jobs"]


def _bet_done_transition_steps() -> list[dict]:
    return _bet_gate_jobs()[BET_GATE_JOB_ID]["steps"]


def test_governance_verify_job_skips_non_authoritative_push_refs() -> None:
    job = _governance_workflow()["jobs"]["governance-verify"]
    assert job.get("if") == (
        "github.event_name != 'push' || github.ref == 'refs/heads/main'"
    )


def test_governance_workflow_triggers_on_ledger_pull_requests() -> None:
    workflow = _governance_workflow()
    triggers = workflow.get("on", workflow.get(True))  # PyYAML 1.1 treats ``on`` as bool.

    assert isinstance(triggers, dict)
    assert "docs/**" in triggers["pull_request"]["paths"]


def test_governance_verify_checkout_has_full_history() -> None:
    """Broad pointer checks still compare ranges and require complete history."""
    steps = _governance_verify_steps()

    checkouts = [step for step in steps if str(step.get("uses", "")).startswith("actions/checkout")]
    assert checkouts, "governance-verify must check out the repository"
    assert all(step.get("with", {}).get("fetch-depth") == 0 for step in checkouts)


def test_bet_done_transition_has_an_independent_status_context() -> None:
    """The transition guard must not share failure state with broad governance checks."""
    jobs = _bet_gate_jobs()

    assert BET_GATE_JOB_ID in jobs
    job = jobs[BET_GATE_JOB_ID]
    assert job.get("name") == BET_GATE_JOB_ID
    assert "needs" not in job
    if BET_GATE_WORKFLOW.exists():
        # 独立 workflow 无 paths 过滤必跑, 无需 if 门(2026-08-26 #2197 根治形态)
        assert job.get("if") is None
    else:
        assert job.get("if") == (
            "github.event_name != 'push' || github.ref == 'refs/heads/main'"
        )

    steps = job["steps"]
    names = [str(step.get("name", "")) for step in steps]
    assert names.count(BET_GATE_STEP_NAME) == 1
    assert "Run full governance verification" not in names
    assert POINTER_DRIFT_STEP_NAME not in names

    checkouts = [step for step in steps if str(step.get("uses", "")).startswith("actions/checkout")]
    assert len(checkouts) == 1
    assert checkouts[0].get("with", {}).get("fetch-depth") == 0

    all_gate_steps = [
        step
        for candidate in jobs.values()
        for step in candidate.get("steps", [])
        if step.get("name") == BET_GATE_STEP_NAME
    ]
    assert len(all_gate_steps) == 1


def test_bet_done_transition_job_has_guard_contract() -> None:
    steps = _bet_done_transition_steps()
    names = [str(step.get("name", "")) for step in steps]
    assert "Install Python gate deps" in names
    assert "Run full governance verification" not in names

    gate_steps = [step for step in steps if step.get("name") == BET_GATE_STEP_NAME]
    assert len(gate_steps) == 1, "exactly one explicitly named BET done-transition gate step"
    gate = gate_steps[0]
    if not BET_GATE_WORKFLOW.exists():
        # 旧形态(job 住 governance-check)需 step 级 if; 独立 workflow(2026-08-26
        # #2197 根治)无 paths 必跑, step 无需 if
        assert gate.get("if") == (
            "github.event_name == 'pull_request' || "
            "(github.event_name == 'push' && github.ref == 'refs/heads/main')"
        )
    script = str(gate.get("run", ""))

    # The gate invokes the real ledger lint, exactly once.
    assert script.count("bin/plan/bet-ledger.py lint") == 1
    assert "python3 bin/plan/bet-ledger.py lint" in script

    # Blocking classification covers exactly the two guard finding families.
    assert "BASE_LEDGER_UNREADABLE" in script
    assert "BET_DONE_" in script
    assert "grep -qE 'BASE_LEDGER_UNREADABLE|BET_DONE_' \"$lint_out\"" in script

    # Full lint output is printed before the classification greps.
    assert "cat " in script and "grep" in script
    assert script.index("cat ") < script.index("grep")

    # The lint's own nonzero exit (historical non-transition debt) stays informational.
    assert "lint_rc=$?" in script
    assert 'exit "$lint_rc"' not in script
    assert "exit $lint_rc" not in script

    # A CLI crash must not masquerade as historical lint debt.  Only the two
    # structural terminal shapes emitted by cmd_lint are accepted.
    assert 'if [[ "$lint_rc" -eq 0 ]]' in script
    assert 'elif [[ "$lint_rc" -eq 1 ]]' in script
    # 2026-09-02 修复: 容忍 main 125 个 pre-existing lint 错误导致 'tail -n 1'
    # 匹配 warning 行失败 → 改为 'tail -n 5 | grep -Eq' 检查末尾 5 行内的
    # 合法收尾 (计数行 / warning 行 / OK 行)
    assert 'tail -n 5 "$lint_out"' in script
    assert "^OK -- " in script
    assert "^[0-9]+ 个问题$" in script
    assert "bet-ledger lint did not complete structurally" in script

    # The isolated gate runs only after its own Python dependencies are installed.
    assert names.index("Install Python gate deps") < names.index(BET_GATE_STEP_NAME)


def test_governance_verify_scopes_strict_pointer_freshness_to_auto_bump_prs() -> None:
    steps = _governance_verify_steps()
    normal_steps = [step for step in steps if step.get("name") == POINTER_DRIFT_STEP_NAME]
    strict_steps = [step for step in steps if step.get("name") == POINTER_STRICT_STEP_NAME]

    assert len(normal_steps) == 1
    normal_script = str(normal_steps[0].get("run", ""))
    assert "python3 bin/gac/check-submodule-pointer-drift.py --json" in normal_script
    assert "--strict" not in normal_script
    assert 'status == "ahead"' in normal_script
    assert '.results | type == "array"' in normal_script

    assert len(strict_steps) == 1
    strict = strict_steps[0]
    assert strict.get("if") == (
        "github.event_name == 'pull_request' && "
        "startsWith(github.head_ref, 'auto/submodule-bump-')"
    )
    strict_script = str(strict.get("run", ""))
    assert "python3 bin/gac/check-submodule-pointer-drift.py --strict" in strict_script


@pytest.mark.parametrize(
    ("payload", "checker_rc", "expected_rc"),
    [
        ({"results": [{"status": "aligned"}]}, 0, 0),
        ({"results": [{"status": "behind"}]}, 0, 0),
        ({"results": [{"status": "ahead"}]}, 0, 1),
        ({"results": [{"status": "behind"}, {"status": "ahead"}]}, 0, 1),
        ({"results": [{"status": "DIVERGED"}]}, 1, 1),
        ({"results": "not-an-array"}, 0, 1),
        ({"results": [{}]}, 0, 1),
        ({"results": [None]}, 0, 1),
        ({"results": [{"status": "unknown"}]}, 0, 1),
        ("not-json", 0, 1),
    ],
)
def test_normal_pointer_step_behavior(
    tmp_path: Path,
    payload: dict | str,
    checker_rc: int,
    expected_rc: int,
) -> None:
    step = next(
        step for step in _governance_verify_steps() if step.get("name") == POINTER_DRIFT_STEP_NAME
    )
    stub_dir = tmp_path / "bin"
    stub_dir.mkdir()
    python_stub = stub_dir / "python3"
    python_stub.write_text(
        '#!/bin/sh\nprintf "%s\\n" "$POINTER_JSON"\nexit "$POINTER_RC"\n',
        encoding="utf-8",
    )
    python_stub.chmod(0o755)
    env = {
        **os.environ,
        "PATH": f"{stub_dir}:{os.environ['PATH']}",
        "POINTER_JSON": json.dumps(payload) if isinstance(payload, dict) else payload,
        "POINTER_RC": str(checker_rc),
        "RUNNER_TEMP": str(tmp_path),
    }
    result = subprocess.run(
        ["bash", "-c", f"set -euo pipefail\n{step['run']}"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == expected_rc, result.stdout + result.stderr


def test_governance_verify_runs_spec_binding_focused_tests() -> None:
    """The transition guard tests are a CI consumer, not a local-only artifact."""
    scripts = [str(step.get("run", "")) for step in _governance_verify_steps()]

    assert any(
        "python3 -m pytest tests/test_spec_binding_lint.py" in script for script in scripts
    )


def test_arbitrary_string_cannot_prove_human_verdict(tmp_path: Path) -> None:
    evidence = _direct_evidence(tmp_path)
    evidence["value"]["human_verdict"] = "decision://human/placeholder"
    matrix = _completion_matrix(
        engineering="VERIFIED",
        operational="PROVEN",
        value="ACCEPTED",
        overall_state="outcome_accepted",
        evidence=evidence,
    )

    state, errors = bl.validate_completion_evidence(matrix, workspace=tmp_path)

    assert state == "blocked"
    assert any("COMPLETION_HUMAN_AUTH_REQUIRED" in error for error in errors)


def test_complete_rejects_engineering_only_matrix_even_with_force(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys,
) -> None:
    evidence = _direct_evidence(tmp_path)
    bet = _bet(status="candidate")
    bet["accepted_specifications"] = [_canonical_binding(tmp_path)]
    bet["completion_evidence"] = _completion_matrix(
        engineering="VERIFIED",
        operational="NOT_PROVEN",
        value="NOT_PROVEN",
        overall_state="blocked",
        evidence=evidence,
    )
    monkeypatch.setattr(bl, "WS", tmp_path)

    rc = bl.cmd_complete(
        _lint_data(bet),
        Namespace(bet_id="BET-TEST", force=True),
    )

    assert rc == 1
    assert "not outcome_accepted" in capsys.readouterr().out


def test_complete_accepts_value_exempt_delivery(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bet = _bet(status="review")
    bet["value_indicator_policy"] = False
    bet["accepted_specifications"] = [_canonical_binding(tmp_path)]
    bet["completion_evidence"] = _completion_matrix(
        engineering="VERIFIED",
        operational="PROVEN",
        value="NOT_PROVEN",
        overall_state="delivery_accepted",
        evidence=_direct_evidence(tmp_path),
    )
    ledger_path = tmp_path / "docs/plans/3y-bet-ledger.yaml"
    ledger_path.parent.mkdir(parents=True)
    ledger_path.write_text("- id: BET-TEST\n  status: review\n", encoding="utf-8")
    monkeypatch.setattr(bl, "WS", tmp_path)
    monkeypatch.setattr(bl, "LEDGER", ledger_path)

    args = type("Args", (), {"bet_id": "BET-TEST", "force": True})()

    assert bl.cmd_complete(_lint_data(bet), args) == 0
    saved = yaml.safe_load(ledger_path.read_text(encoding="utf-8"))
    assert next(entry for entry in saved if entry["id"] == "BET-TEST")["status"] == "done"


@pytest.mark.parametrize("policy", ["false", 0, None, []], ids=["string", "number", "null", "list"])
def test_complete_rejects_non_boolean_value_indicator_policy_without_persisting(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys,
    policy: object,
) -> None:
    bet = _bet(status="review")
    bet["value_indicator_policy"] = policy
    bet["accepted_specifications"] = [_canonical_binding(tmp_path)]
    bet["completion_evidence"] = _completion_matrix(
        engineering="VERIFIED",
        operational="PROVEN",
        value="NOT_PROVEN",
        overall_state="delivery_accepted",
        evidence=_direct_evidence(tmp_path),
    )
    ledger_path = tmp_path / "docs/plans/3y-bet-ledger.yaml"
    ledger_path.parent.mkdir(parents=True)
    ledger_path.write_text(
        "- id: BET-OTHER\n  status: review\n- id: BET-TEST\n  status: review\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(bl, "WS", tmp_path)
    monkeypatch.setattr(bl, "LEDGER", ledger_path)

    rc = bl.cmd_complete(_lint_data(bet), Namespace(bet_id="BET-TEST", force=True))

    assert rc == 1
    assert (
        "[complete] ❌ BET-TEST.value_indicator_policy: "
        "VALUE_INDICATOR_POLICY_TYPE: value_indicator_policy must be a boolean"
    ) in capsys.readouterr().out
    saved = yaml.safe_load(ledger_path.read_text(encoding="utf-8"))
    assert next(entry for entry in saved if entry["id"] == "BET-TEST")["status"] == "review"


def test_complete_requires_matrix_even_with_force(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys,
) -> None:
    bet = _bet(status="candidate")
    bet["accepted_specifications"] = [_canonical_binding(tmp_path)]
    monkeypatch.setattr(bl, "WS", tmp_path)

    rc = bl.cmd_complete(
        _lint_data(bet),
        Namespace(bet_id="BET-TEST", force=True),
    )

    assert rc == 1
    assert "COMPLETION_EVIDENCE_REQUIRED" in capsys.readouterr().out


def _sign_attestation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, tamper: bool = False) -> tuple[Path, Path]:
    """Generate an ephemeral SSH keypair and sign a valid attestation receipt.

    Returns (receipt_path, allowed_signers_path). When ``tamper`` is True the
    signature bytes are corrupted so verification must fail.
    """
    key_dir = tmp_path / "ssh-keys"
    key_dir.mkdir(parents=True, exist_ok=True)
    key_path = key_dir / "id_ed25519"
    subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(key_path)], check=True)

    receipt: dict[str, Any] = {
        "schema_version": "human-attestation/v1",
        "principal_id": "principal:tester",
        "verdict": "accept",
        "episode_id": "episode:test-001",
        "signal_event_id": "evt_test_signal",
        "observed_at": "2026-08-21T12:00:00Z",
        "signer_identity": "tester",
    }
    message = "\n".join(f"{k}={receipt[k]}" for k in bl.HUMAN_ATTESTATION_MESSAGE_FIELDS) + "\n"
    message_path = tmp_path / "message.txt"
    message_path.write_text(message, encoding="utf-8")
    subprocess.run(
        [
            "ssh-keygen", "-Y", "sign", "-f", str(key_path),
            "-n", "omostation-human-attestation", str(message_path),
        ],
        capture_output=True,
        check=True,
    )
    # ssh-keygen -Y sign writes to <message_path>.sig; reconstruct blob from disk.
    sig_path = Path(str(message_path) + ".sig")
    sig_bytes = sig_path.read_bytes()
    if tamper:
        sig_bytes = sig_bytes[:-4] + b"\x00\x00\x00\x00"
    receipt["signature_b64"] = base64.b64encode(sig_bytes).decode()

    allowed_signers = tmp_path / "allowed-signers"
    pub = (key_dir / "id_ed25519.pub").read_text(encoding="utf-8").strip()
    allowed_signers.write_text(f"tester {pub}\n", encoding="utf-8")
    monkeypatch.setattr(bl, "HUMAN_ATTESTATION_ALLOWED_SIGNERS", str(allowed_signers))

    receipt_path = tmp_path / "attestation.yaml"
    receipt_path.write_text(yaml.safe_dump(receipt), encoding="utf-8")
    return receipt_path, allowed_signers


def test_valid_human_attestation_makes_value_accepted(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    evidence = _direct_evidence(tmp_path)
    receipt_path, _ = _sign_attestation(tmp_path, monkeypatch)
    evidence["value"] = {
        "real_signal": {"ref": "receipt://evidence/value-real_signal.json", "sha256": "sha256:0" * 8},
        "human_verdict": {"ref": "receipt://evidence/value-human_verdict.json", "sha256": "sha256:0" * 8},
        "revision": {"ref": "receipt://evidence/value-revision.json", "sha256": "sha256:0" * 8},
        "time_burden": {"ref": "receipt://evidence/value-time_burden.json", "sha256": "sha256:0" * 8},
        "attestation": {
            "ref": f"receipt://{receipt_path.relative_to(tmp_path)}",
            "sha256": f"sha256:{bl._file_sha256(receipt_path)}",
        },
    }
    for key in ("real_signal", "human_verdict", "revision", "time_burden"):
        p = tmp_path / "evidence" / f"value-{key}.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(f'{{"kind":"{key}"}}\n', encoding="utf-8")
        evidence["value"][key] = {"ref": f"receipt://evidence/value-{key}.json", "sha256": f"sha256:{bl._file_sha256(p)}"}

    matrix = _completion_matrix(
        engineering="VERIFIED",
        operational="PROVEN",
        value="ACCEPTED",
        overall_state="outcome_accepted",
        evidence=evidence,
    )
    state, errors = bl.validate_completion_evidence(matrix, workspace=tmp_path)
    assert errors == []
    assert state == "outcome_accepted"


def test_tampered_attestation_signature_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    evidence = _direct_evidence(tmp_path)
    receipt_path, _ = _sign_attestation(tmp_path, monkeypatch, tamper=True)
    for key in ("real_signal", "human_verdict", "revision", "time_burden"):
        p = tmp_path / "evidence" / f"value-{key}.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(f'{{"kind":"{key}"}}\n', encoding="utf-8")
        evidence["value"][key] = {"ref": f"receipt://evidence/value-{key}.json", "sha256": f"sha256:{bl._file_sha256(p)}"}
    evidence["value"]["attestation"] = {
        "ref": f"receipt://{receipt_path.relative_to(tmp_path)}",
        "sha256": f"sha256:{bl._file_sha256(receipt_path)}",
    }

    matrix = _completion_matrix(
        engineering="VERIFIED",
        operational="PROVEN",
        value="ACCEPTED",
        overall_state="outcome_accepted",
        evidence=evidence,
    )
    state, errors = bl.validate_completion_evidence(matrix, workspace=tmp_path)
    assert state == "blocked"
    assert any("COMPLETION_HUMAN_AUTH_SIGNATURE_INVALID" in error for error in errors)


def test_missing_attestation_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    evidence = _direct_evidence(tmp_path)
    for key in ("real_signal", "human_verdict", "revision", "time_burden"):
        p = tmp_path / "evidence" / f"value-{key}.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(f'{{"kind":"{key}"}}\n', encoding="utf-8")
        evidence["value"][key] = {"ref": f"receipt://evidence/value-{key}.json", "sha256": f"sha256:{bl._file_sha256(p)}"}

    matrix = _completion_matrix(
        engineering="VERIFIED",
        operational="PROVEN",
        value="ACCEPTED",
        overall_state="outcome_accepted",
        evidence=evidence,
    )
    state, errors = bl.validate_completion_evidence(matrix, workspace=tmp_path)
    assert state == "blocked"
    assert any("COMPLETION_HUMAN_AUTH_REQUIRED" in error for error in errors)
