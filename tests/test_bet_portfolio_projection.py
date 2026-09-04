"""T1-08 Portfolio projection fixtures."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).parents[1]
MOD = ROOT / "bin" / "plan" / "portfolio_projection.py"
SPEC = importlib.util.spec_from_file_location("portfolio_projection", MOD)
assert SPEC and SPEC.loader
PP = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = PP
SPEC.loader.exec_module(PP)


def _ledger() -> dict:
    return {
        "meta": {"total_bets": 2},
        "vision": {"id": "VISION-TEST"},
        "objectives": [
            {
                "id": "OBJ-TRUST",
                "key_results": [{"id": "KR-TRUST-CHAIN-COVERAGE", "status": "proven"}],
            }
        ],
        "campaigns": [{"id": "CMP-W0-PORTFOLIO-TRUTH"}],
        "milestones": [
            {
                "id": "MS-W0-CONTRACT",
                "required_bets": ["BET-A"],
                "required_krs": ["KR-TRUST-CHAIN-COVERAGE"],
                "status": "derived",
            }
        ],
        "bets": [
            {"id": "BET-Y1Q4-T1-08", "status": "candidate", "human_gate": False},
            {"id": "BET-A", "status": "done", "human_gate": False},
        ],
    }


def _ws(tmp_path: Path, ledger: dict, *, surfaces: list[dict] | None = None) -> Path:
    (tmp_path / "docs" / "plans").mkdir(parents=True)
    (tmp_path / ".omo" / "_truth" / "registry").mkdir(parents=True)
    ledger_bytes = yaml.safe_dump(ledger, sort_keys=True).encode()
    (tmp_path / "docs" / "plans" / "3y-bet-ledger.yaml").write_bytes(ledger_bytes)
    doc = {
        "status": "active",
        "surfaces": surfaces
        if surfaces is not None
        else [
            {
                "name": "omo-goal-create",
                "mode": "brokered",
                "broker_ref": "projects/omo/src/omo/omo_ingress.py:create_goal",
                "mutation_target": ".omo/goals/current.yaml",
            }
        ],
    }
    # multi-doc like production
    (tmp_path / ".omo" / "_truth" / "registry" / "mutation-surfaces.yaml").write_text(
        "status: active\n---\n" + yaml.safe_dump(doc),
        encoding="utf-8",
    )
    return tmp_path


def test_three_outputs_share_source_digest(tmp_path: Path) -> None:
    ws = _ws(tmp_path, _ledger())
    raw = (ws / "docs/plans/3y-bet-ledger.yaml").read_bytes()
    b1 = PP.build_bundle(raw, ws)
    b2 = PP.build_bundle(raw, ws)
    assert b1.source_digest == b2.source_digest
    assert b1.goals_bytes == b2.goals_bytes
    assert b1.markdown_bytes == b2.markdown_bytes
    assert b1.control_bytes == b2.control_bytes
    goals = yaml.safe_load(b1.goals_bytes)
    control = json.loads(b1.control_bytes)
    assert goals["source_digest"] == control["source_digest"] == b1.source_digest
    assert b1.source_digest.encode() in b1.markdown_bytes


def test_broker_missing_marks_omo_unavailable(tmp_path: Path) -> None:
    ws = _ws(tmp_path, _ledger())  # only goals owned
    b = PP.build_bundle((ws / "docs/plans/3y-bet-ledger.yaml").read_bytes(), ws)
    assert b.broker_ok is False
    assert "PORTFOLIO_BROKER_OWNER_MISSING" in b.broker_reason
    control = json.loads(b.control_bytes)
    assert control["status"] == "unavailable"


def test_markdown_apply_and_check_detects_drift(tmp_path: Path) -> None:
    ws = _ws(tmp_path, _ledger())
    raw = (ws / "docs/plans/3y-bet-ledger.yaml").read_bytes()
    b = PP.build_bundle(raw, ws)
    PP.apply_markdown(ws, b)
    assert PP.check_bundle(ws, b) == []
    md = ws / "docs/plans/3Y-BET-PORTFOLIO.md"
    md.write_bytes(md.read_bytes() + b"x")
    errs = PP.check_bundle(ws, b)
    assert any(e.startswith("PROJECTION_DRIFT") for e in errs)


def test_direct_omo_write_helper_forbidden() -> None:
    with pytest.raises(PermissionError, match="PORTFOLIO_DIRECT_IO_FORBIDDEN"):
        PP.assert_no_direct_omo_write(Path(".omo/_control/portfolio-status.json"))


def test_apply_omo_halts_without_broker(tmp_path: Path) -> None:
    ws = _ws(tmp_path, _ledger())
    b = PP.build_bundle((ws / "docs/plans/3y-bet-ledger.yaml").read_bytes(), ws)
    with pytest.raises(SystemExit, match="PORTFOLIO_BROKER_OWNER_MISSING"):
        PP.apply_omo_via_broker(ws, b)


def test_missing_ledger_is_unavailable(tmp_path: Path) -> None:
    rc = PP.main(["--workspace", str(tmp_path), "--check"])
    assert rc == 2


def test_cli_check_and_apply_markdown(tmp_path: Path) -> None:
    ws = _ws(tmp_path, _ledger())
    rc = PP.main(["--workspace", str(ws), "--apply-markdown", "--check"])
    assert rc == 0
    assert (ws / "docs/plans/3Y-BET-PORTFOLIO.md").is_file()


def test_broker_ok_when_both_targets_registered(tmp_path: Path) -> None:
    surfaces = [
        {
            "name": "goals",
            "mode": "brokered",
            "broker_ref": "x:goals",
            "mutation_target": ".omo/goals/current.yaml",
        },
        {
            "name": "control",
            "mode": "brokered",
            "broker_ref": "x:control",
            "mutation_target": ".omo/_control/portfolio-status.json",
        },
    ]
    ws = _ws(tmp_path, _ledger(), surfaces=surfaces)
    ok, reason = PP.broker_owns_portfolio_targets(ws)
    assert ok is True
    assert reason == "broker_ok"
