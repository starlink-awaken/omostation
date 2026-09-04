"""T1-07 Portfolio legacy BET migration manifest tests."""

from __future__ import annotations

import hashlib
import importlib.util
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).parents[1]
MOD_PATH = ROOT / "bin" / "plan" / "portfolio_migration.py"
SPEC = importlib.util.spec_from_file_location("portfolio_migration", MOD_PATH)
assert SPEC and SPEC.loader
PM = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = PM
SPEC.loader.exec_module(PM)


def _digest(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _ledger(*bets: dict) -> dict:
    return {"meta": {"total_bets": len(bets)}, "bets": list(bets)}


def test_inventory_covers_every_id_exactly_once() -> None:
    ledger = _ledger(
        {"id": "BET-A", "status": "done"},
        {"id": "BET-B", "status": "blocked"},
        {"id": "BET-C", "status": "candidate"},
        {"id": "BET-Y1Q4-T1-07", "status": "candidate"},
    )
    rows = PM.inventory(ledger)
    assert [r["id"] for r in rows] == ["BET-A", "BET-B", "BET-C", "BET-Y1Q4-T1-07"]


def test_classify_terminal_blocked_and_w0() -> None:
    assert PM.classify({"id": "X", "status": "done"})[0] == "reuse"
    assert PM.classify({"id": "Y", "status": "blocked"})[0] == "defer"
    assert PM.classify({"id": "BET-Y1Q4-T1-07", "status": "candidate"})[0] == "continue"
    assert PM.classify({"id": "Z", "status": "candidate"})[0] == "defer"
    assert PM.classify({"id": "M", "status": None})[0] == "stop"


def test_manifest_deterministic_and_complete() -> None:
    ledger = _ledger(
        {"id": "BET-Z", "status": "failed"},
        {"id": "BET-A", "status": "candidate"},
        {"id": "BET-Y1Q4-T1-04", "status": "done"},
    )
    raw = yaml.safe_dump(ledger, sort_keys=True).encode()
    m1 = PM.build_manifest_from_bytes(raw)
    m2 = PM.build_manifest_from_bytes(raw)
    assert m1.to_dict() == m2.to_dict()
    assert m1.bet_count == 3
    assert [r.bet_id for r in m1.rows] == ["BET-A", "BET-Y1Q4-T1-04", "BET-Z"]
    assert m1.source_digest == _digest(raw)
    assert {r.disposition for r in m1.rows} <= PM.DISPOSITIONS


def test_duplicate_id_is_scope_drift() -> None:
    ledger = _ledger({"id": "BET-A", "status": "done"}, {"id": "BET-A", "status": "candidate"})
    with pytest.raises(ValueError, match="MIGRATION_SCOPE_DRIFT"):
        PM.inventory(ledger)


def test_apply_unconditionally_rejected() -> None:
    with pytest.raises(SystemExit) as ei:
        PM.main(["--apply", "--dry-run"])
    assert "MIGRATION_APPLY_NOT_AUTHORIZED" in str(ei.value)


def test_batch_over_eight_rejected() -> None:
    with pytest.raises(SystemExit) as ei:
        PM.reject_batch_size(9)
    assert "MIGRATION_SCOPE_DRIFT" in str(ei.value)


def test_dry_run_cli_zero_mutation(tmp_path: Path) -> None:
    ledger = _ledger(
        {"id": "BET-A", "status": "done"},
        {"id": "BET-B", "status": "candidate"},
    )
    ledger_path = tmp_path / "ledger.yaml"
    before = yaml.safe_dump(ledger, sort_keys=True).encode()
    ledger_path.write_bytes(before)
    out = tmp_path / "manifest.yaml"
    rc = PM.main(["--dry-run", "--yaml", "--ledger", str(ledger_path), "--write-manifest", str(out)])
    assert rc == 0
    assert ledger_path.read_bytes() == before
    assert out.exists()
    payload = yaml.safe_load(out.read_text())
    assert payload["bet_count"] == 2
    assert payload["source_digest"] == _digest(before)
