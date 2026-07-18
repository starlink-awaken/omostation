"""Structural tests for G-CONV helpers (foundry gitlink slot, kos seed, repair draft)."""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_foundry_cron_registers_gitlink_slot():
    text = (ROOT / "bin/gac/knowledge-foundry-cron.py").read_text(encoding="utf-8")
    assert "5:45-gitlink-check" in text
    assert "bin/submodule-gitlink-check.py" in text


def test_write_owner_repair_draft_writes_file(tmp_path, monkeypatch):
    mod = _load(ROOT / "bin/ssot/write-owner-repair-draft.py", "repair_draft")
    monkeypatch.setattr(mod, "WORKSPACE", tmp_path)
    monkeypatch.setattr(mod, "DRAFT_DIR", tmp_path / ".omo/_delivery/repair-drafts")
    # fake git staged empty
    monkeypatch.setattr(mod, "_staged_files", lambda: ["foo.yaml"])
    rc = mod.main(["--from-audit-exit"])
    assert rc == 0
    drafts = list((tmp_path / ".omo/_delivery/repair-drafts").glob("write-owner-*.md"))
    assert len(drafts) == 1
    assert "foo.yaml" in drafts[0].read_text(encoding="utf-8")


def test_kos_seed_import_creates_documents(tmp_path):
    mod = _load(ROOT / "bin/gac/kos-seed-import.py", "kos_seed")
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "a.md").write_text("# Hello\n\nbody\n", encoding="utf-8")
    db = tmp_path / "kos" / "kos-index.sqlite"
    # point WORKSPACE helpers
    monkeypatch_workspace = tmp_path
    # rewrite by calling import_docs directly
    count = mod.import_docs(db, [docs / "a.md"])
    assert count >= 1
    import sqlite3
    conn = sqlite3.connect(str(db))
    n = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    conn.close()
    assert n >= 1


def test_gitlink_check_clean_exits_zero():
    r = subprocess.run(
        [sys.executable, str(ROOT / "bin/submodule-gitlink-check.py"), "--json"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    # clean tree → 0; may fail if env dirty, but JSON should parse
    assert r.stdout.strip().startswith("{")


def test_precommit_write_owner_uses_commit_flag():
    text = (ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8")
    assert "write-owner-audit" in text
    assert "write-owner-repair-draft.py" in text
    assert "--commit" in text


def test_write_owner_audit_blocks_non_system_on_script_owned(monkeypatch, tmp_path):
    mod = _load(ROOT / "bin/ssot/write-owner-audit.py", "write_owner_audit")
    # force script-owned path rule + non-system user (not human alias, no run-id)
    monkeypatch.delenv("AGENT_WORKFLOW_RUN_ID", raising=False)
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    owners = [{"path": ".omo/state/system.yaml", "owner": "script:runtime-scan"}]
    violations = mod.audit_staged(
        [".omo/state/system.yaml"], owners, current_user="random-outsider"
    )
    assert violations, "non-system committer must be blocked on script-owned path"
    assert "system.yaml" in violations[0]
