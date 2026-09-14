"""Guardrails for bin/ssot/sync-bet-digests.py — forbid status/done_at mutation."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
SYNC = ROOT / "bin" / "ssot" / "sync-bet-digests.py"


@pytest.fixture()
def sync_mod(monkeypatch):
    import importlib.util

    spec = importlib.util.spec_from_file_location("sync_bet_digests", SYNC)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def test_apply_rewrites_digest_without_status_change(tmp_path: Path, sync_mod):
    target = tmp_path / "spec.md"
    target.write_text("# hello\n", encoding="utf-8")
    actual = _sha(target)
    stale = "sha256:" + ("ab" * 32)

    ledger = tmp_path / "ledger.yaml"
    ledger.write_text(
        f"""bets:
- id: BET-TEST-1
  status: done
  done_at: '2026-09-03'
  accepted_specifications:
  - spec_ref: repo://{target.name}
    content_digest: {stale}
""",
        encoding="utf-8",
    )

    # Point resolve_ref into tmp by monkeypatching REPO
    sync_mod.REPO = tmp_path
    sync_mod.LEDGER = ledger

    mismatches = sync_mod.scan_ledger(ledger)
    assert len(mismatches) == 1
    assert mismatches[0]["actual"] == actual

    fixed = sync_mod.apply_fixes(mismatches, ledger)
    assert fixed >= 1

    data = yaml.safe_load(ledger.read_text(encoding="utf-8"))
    bet = data["bets"][0]
    assert bet["status"] == "done"
    assert bet["done_at"] == "2026-09-03"
    assert bet["accepted_specifications"][0]["content_digest"] == actual
    # Still a single bet — no yaml.dump rewrite catastrophe
    assert len(data["bets"]) == 1


def test_apply_refuses_if_status_would_change(tmp_path: Path, sync_mod, monkeypatch):
    """Integrity check catches any post-apply status drift."""
    ledger = tmp_path / "ledger.yaml"
    before = """bets:
- id: BET-TEST-1
  status: done
  done_at: '2026-09-03'
"""
    after = """bets:
- id: BET-TEST-1
  status: candidate
  done_at: '2026-09-03'
"""
    with pytest.raises(RuntimeError, match="status/done_at"):
        sync_mod.assert_structural_invariants(before, after)


def test_apply_refuses_bet_deletion(sync_mod):
    before = """bets:
- id: BET-A
  status: done
- id: BET-B
  status: candidate
"""
    after = """bets:
- id: BET-A
  status: done
"""
    with pytest.raises(RuntimeError, match="bet count"):
        sync_mod.assert_structural_invariants(before, after)
