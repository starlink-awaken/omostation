"""Drive the shipped Plan→BET→workflow→closeout→retro bind entry points."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
CHAIN_MOD = ROOT / "bin/plan/chain_bind.py"
CHECK_CLI = ROOT / "bin/plan/chain-bind-check.py"
LEDGER_MOD = ROOT / "bin/plan/bet-ledger.py"
WORKFLOW = ROOT / "bin/agent-workflow.py"
NORTH = "织星是夏明星一个人的业务操作系统。"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


BIND = _load(CHAIN_MOD, "chain_bind_under_test")
LEDGER = _load(LEDGER_MOD, "bet_ledger_under_test")


def _run(cmd: list[str], *, env: dict[str, str] | None = None, cwd: Path = ROOT):
    merged = {k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"}
    if env:
        merged.update(env)
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, env=merged)


def test_evaluate_bind_halts_each_missing_link() -> None:
    missing_bet = BIND.evaluate_bind(
        bet_id="BET-Y1Q1-T6-02",
        run_bet_id="",
        north_star_present=True,
        retro_required=True,
        retro_present=True,
    )
    assert missing_bet.ok is False
    assert "missing_bet_binding" in missing_bet.reasons

    missing_star = BIND.evaluate_bind(
        bet_id="BET-Y1Q1-T6-02",
        run_bet_id="BET-Y1Q1-T6-02",
        north_star_present=False,
        retro_required=True,
        retro_present=True,
    )
    assert missing_star.ok is False
    assert "missing_north_star_pointer" in missing_star.reasons

    missing_retro = BIND.evaluate_bind(
        bet_id="BET-Y1Q1-T6-02",
        run_bet_id="BET-Y1Q1-T6-02",
        north_star_present=True,
        retro_required=True,
        retro_present=False,
    )
    assert missing_retro.ok is False
    assert "missing_retro" in missing_retro.reasons

    ok = BIND.evaluate_bind(
        bet_id="BET-Y1Q1-T6-02",
        run_bet_id="BET-Y1Q1-T6-02",
        north_star_present=True,
        retro_required=True,
        retro_present=True,
    )
    assert ok.ok is True
    assert ok.reasons == []


def test_start_requires_bet_uses_shipped_predicate() -> None:
    denied = BIND.start_requires_bet("governance-state-mutation", "")
    assert denied.ok is False
    allowed = BIND.start_requires_bet("governance-state-mutation", "BET-Y1Q1-T6-02")
    assert allowed.ok is True
    exempt = BIND.start_requires_bet("observer-audit", "")
    assert exempt.ok is True
    waived = BIND.start_requires_bet("governance-state-mutation", "", env={"AGCP_REQUIREMENT_ITERATION_GATE": "0"})
    assert waived.ok is True


def test_chain_bind_check_cli_self_check_and_start_gate() -> None:
    self_check = _run(["python3", str(CHECK_CLI), "self-check"])
    assert self_check.returncode == 0, self_check.stdout + self_check.stderr
    assert "PASS" in self_check.stdout

    missing = _run(
        [
            "python3",
            str(CHECK_CLI),
            "start",
            "--workflow",
            "governance-state-mutation",
        ]
    )
    assert missing.returncode != 0
    assert "missing_bet_id" in missing.stdout

    present = _run(
        [
            "python3",
            str(CHECK_CLI),
            "start",
            "--workflow",
            "governance-state-mutation",
            "--bet",
            "BET-Y1Q1-T6-02",
        ]
    )
    assert present.returncode == 0


def test_complete_cli_fixture_paths(tmp_path: Path) -> None:
    bet = tmp_path / "bet.json"
    bet.write_text(json.dumps({"id": "BET-FIXTURE", "retro": "required"}), encoding="utf-8")
    retro = tmp_path / "BET-FIXTURE.md"
    missing = _run(
        [
            "python3",
            str(CHECK_CLI),
            "complete",
            "--bet-json",
            str(bet),
            "--retro-path",
            str(tmp_path / "missing.md"),
            "--north-star",
            "yes",
        ]
    )
    assert missing.returncode != 0
    assert "missing_retro" in missing.stdout

    retro.write_text("# retro\n", encoding="utf-8")
    unbound = _run(
        [
            "python3",
            str(CHECK_CLI),
            "complete",
            "--bet-json",
            str(bet),
            "--retro-path",
            str(retro),
            "--north-star",
            "yes",
            "--missing-run-bind",
        ]
    )
    assert unbound.returncode != 0
    assert "missing_bet_binding" in unbound.stdout

    ok = _run(
        [
            "python3",
            str(CHECK_CLI),
            "complete",
            "--bet-json",
            str(bet),
            "--retro-path",
            str(retro),
            "--north-star",
            "yes",
        ]
    )
    assert ok.returncode == 0, ok.stdout + ok.stderr


def test_agent_workflow_start_requires_bet_and_persists_field() -> None:
    env_on = {"AGCP_REQUIREMENT_ITERATION_GATE": "1"}
    blocked = _run(
        [
            "uv",
            "run",
            "--with",
            "pyyaml",
            "python",
            str(WORKFLOW),
            "start",
            "project-doc-change",
            "--profile",
            "docs-agent",
            "--objective",
            "no bet",
            "--dry-run",
            "--json",
        ],
        env=env_on,
    )
    assert blocked.returncode != 0, blocked.stdout
    assert "missing_bet_id" in blocked.stderr or "missing_bet_id" in blocked.stdout

    started = _run(
        [
            "uv",
            "run",
            "--with",
            "pyyaml",
            "python",
            str(WORKFLOW),
            "start",
            "project-doc-change",
            "--profile",
            "docs-agent",
            "--bet",
            "BET-Y1Q4-T1-08",
            "--objective",
            "persist bet",
            "--dry-run",
            "--json",
        ],
        env=env_on,
    )
    assert started.returncode == 0, started.stderr
    record = json.loads(started.stdout)
    assert record.get("bet_id") == "BET-Y1Q4-T1-08"
    # north_star_ref may be omitted on dry-run start payloads; chain perception still owns it.
    if record.get("north_star_ref") is not None:
        assert record.get("north_star_ref") == BIND.NORTH_STAR_REF


def test_bet_ledger_complete_halts_without_chain(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace = tmp_path / "ws"
    (workspace / "docs" / "plans").mkdir(parents=True)
    (workspace / ".omo" / "_knowledge" / "retros").mkdir(parents=True)
    (workspace / ".omo" / "_delivery" / "agent-workflows" / "runs").mkdir(parents=True)
    (workspace / "docs" / "STRATEGY-3YEAR-PLAN-2026H2-2029.md").write_text(NORTH + "\n", encoding="utf-8")
    monkeypatch.setattr(LEDGER, "WS", workspace)
    spec_rel = "docs/superpowers/specs/fixture-bet-complete-design.md"
    spec_body = (
        "---\n"
        "schema_version: specification/v1\n"
        "spec_version: 1.0.0\n"
        "status: accepted\n"
        "bet_id: BET-FIXTURE\n"
        "implementation_authorized: true\n"
        "---\n\n"
        "# Fixture Spec\n"
    )
    spec_path = workspace / spec_rel
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.write_text(spec_body, encoding="utf-8")
    import hashlib

    digest = "sha256:" + hashlib.sha256(spec_path.read_bytes()).hexdigest()
    bet = {
        "id": "BET-FIXTURE",
        "status": "in_progress",
        "title": "fixture",
        "retro": "required",
        "write_surfaces": [],
        "value_indicator_policy": False,
        "accepted_specifications": [
            {
                "spec_ref": f"repo://{spec_rel}",
                "spec_version": "1.0.0",
                "content_digest": digest,
                "decision_ref": "decision://accepted/BET-FIXTURE",
            }
        ],
    }
    data = {"bets": [bet]}
    args = SimpleNamespace(bet_id="BET-FIXTURE", force=False)
    # no retro, no bound run
    rc = LEDGER.cmd_complete(data, args)
    assert rc != 0

    (workspace / ".omo" / "_knowledge" / "retros" / "BET-FIXTURE.md").write_text("# retro\n", encoding="utf-8")
    rc = LEDGER.cmd_complete(data, args)
    assert rc != 0  # still missing run bind

    run = {
        "run_id": "run-fixture",
        "status": "active",
        "bet_id": "BET-FIXTURE",
        "workflow_id": "project-doc-change",
    }
    (workspace / ".omo" / "_delivery" / "agent-workflows" / "runs" / "run-fixture.yaml").write_text(
        yaml.safe_dump(run), encoding="utf-8"
    )
    # cmd_complete will try to rewrite 3y-bet-ledger.yaml under WS
    (workspace / "docs" / "plans" / "3y-bet-ledger.yaml").write_text(yaml.safe_dump(data), encoding="utf-8")
    monkeypatch.setattr(LEDGER, "LEDGER", workspace / "docs" / "plans" / "3y-bet-ledger.yaml")
    # Chain-bind predicate itself must pass once retro + bound run + north-star exist.
    # Full cmd_complete also requires completion_evidence matrix (covered by T1-06 fixtures).
    verdict = BIND.evaluate_complete(bet, workspace)
    assert verdict.ok, verdict.reasons


def test_perception_fields_include_north_star() -> None:
    fields = BIND.perception_fields(ROOT)
    assert NORTH in fields["north_star"]
    assert fields["north_star_ref"] == "docs/STRATEGY-3YEAR-PLAN-2026H2-2029.md"
    assert "bound_bet" in fields
    assert "overdue_retros" in fields
    assert fields["north_star_present"] is True
    assert fields["bound_bet"] != "missing-bet"


def test_perception_closed_bound_run_is_not_missing_bet(tmp_path: Path) -> None:
    runs = tmp_path / ".omo" / "_delivery" / "agent-workflows" / "runs"
    runs.mkdir(parents=True)
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "STRATEGY-3YEAR-PLAN-2026H2-2029.md").write_text(NORTH + "\n", encoding="utf-8")
    (runs / "closed.yaml").write_text(
        yaml.safe_dump(
            {
                "run_id": "closed-1",
                "status": "ok",
                "bet_id": "BET-Y1Q1-T6-03",
            }
        ),
        encoding="utf-8",
    )
    fields = BIND.perception_fields(tmp_path)
    assert fields["bound_state"] == "closed"
    assert fields["bound_bet"] == "BET-Y1Q1-T6-03 (closed)"
    assert "missing-bet" not in fields["bound_bet"]


def test_perception_prefers_latest_closed_bound_run(tmp_path: Path) -> None:
    """Filename sort would pick T6-02; recency must pick T6-03."""
    runs = tmp_path / ".omo" / "_delivery" / "agent-workflows" / "runs"
    runs.mkdir(parents=True)
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "STRATEGY-3YEAR-PLAN-2026H2-2029.md").write_text(NORTH + "\n", encoding="utf-8")
    (runs / "aaa-older.yaml").write_text(
        yaml.safe_dump(
            {
                "run_id": "aaa-older",
                "status": "ok",
                "bet_id": "BET-Y1Q1-T6-02",
                "updated_at": "2026-08-15T12:00:00Z",
            }
        ),
        encoding="utf-8",
    )
    (runs / "zzz-newer.yaml").write_text(
        yaml.safe_dump(
            {
                "run_id": "zzz-newer",
                "status": "blocked",
                "bet_id": "BET-Y1Q1-T6-03",
                "updated_at": "2026-08-16T01:27:36Z",
            }
        ),
        encoding="utf-8",
    )
    fields = BIND.perception_fields(tmp_path)
    assert fields["bound_state"] == "closed"
    assert fields["bound_bet"] == "BET-Y1Q1-T6-03 (closed)"
    assert fields["closed_bets"][0] == "BET-Y1Q1-T6-03"
    assert BIND.run_recency_key({"updated_at": "2026-08-16T01:27:36Z"}) > BIND.run_recency_key(
        {"updated_at": "2026-08-15T12:00:00Z"}
    )


def test_omo_cli_start_requires_bet_same_as_wrapper() -> None:
    env_on = {
        "AGCP_REQUIREMENT_ITERATION_GATE": "1",
        "PYTHONPATH": str(ROOT / "projects/omo/src"),
    }
    blocked = _run(
        [
            sys.executable,
            "-c",
            (
                "from omo.workflow.cli import main; "
                "raise SystemExit(main(['start','project-doc-change',"
                "'--profile','docs-agent','--objective','no bet',"
                "'--dry-run','--json']))"
            ),
        ],
        env=env_on,
    )
    assert blocked.returncode != 0, blocked.stdout + blocked.stderr
    assert "missing_bet_id" in blocked.stderr or "missing_bet_id" in blocked.stdout

    started = _run(
        [
            sys.executable,
            "-c",
            (
                "from omo.workflow.cli import main; "
                "raise SystemExit(main(['start','project-doc-change',"
                "'--profile','docs-agent','--bet','BET-Y1Q4-T1-08',"
                "'--objective','persist','--dry-run','--json']))"
            ),
        ],
        env=env_on,
    )
    assert started.returncode == 0, started.stderr
    record = json.loads(started.stdout)
    assert record.get("bet_id") == "BET-Y1Q4-T1-08"


def test_gen_agent_redlines_includes_vision_to_retro(tmp_path: Path) -> None:
    out = tmp_path / "agent-redlines.md"
    result = _run(
        [sys.executable, str(ROOT / "bin/mof/gen-agent-redlines.py"), str(out)],
        cwd=ROOT,
    )
    assert result.returncode == 0, result.stderr
    text = out.read_text(encoding="utf-8")
    assert "vision-to-retro-chain" in text
    assert "bin/plan/chain-bind-check.py" in text


def test_weekly_documents_audit_closeout_is_governance_exempt(tmp_path, monkeypatch):
    """documents-consumer-audit-weekly (ADR-0441 primitive 3) rides the governance-evolve lane."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "docs/plans").mkdir(parents=True)
    (tmp_path / "docs/plans/3y-bet-ledger.yaml").write_text(
        "bets:\n  - id: BET-Y1Q3-T10-69\n    track: T10-MATURITY\n", encoding="utf-8"
    )
    run = {"workflow_id": "documents-consumer-audit-weekly", "bet_id": ""}
    verdict = BIND.evaluate_closeout(run, tmp_path, status="ok")
    assert verdict.ok, f"weekly audit must be governance-exempt, got {verdict.reasons}"


def test_convergence_pulse_closeout_is_governance_exempt(tmp_path, monkeypatch):
    """convergence-pulse-weekly (ADR-0443) rides the governance-evolve lane."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "docs/plans").mkdir(parents=True)
    (tmp_path / "docs/plans/3y-bet-ledger.yaml").write_text(
        "bets:\n  - id: BET-Y1Q3-T10-69\n    track: T10-MATURITY\n", encoding="utf-8"
    )
    run = {"workflow_id": "convergence-pulse-weekly", "bet_id": ""}
    verdict = BIND.evaluate_closeout(run, tmp_path, status="ok")
    assert verdict.ok, f"convergence pulse must be governance-exempt, got {verdict.reasons}"
