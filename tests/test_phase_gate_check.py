"""Tests for ADR-0223 phase-gate-check (real module)."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load():
    path = ROOT / "bin/gac/phase-gate-check.py"
    name = "phase_gate_check_mod"
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_blocks_delivery_when_phase2_locked(tmp_path: Path):
    mod = _load()
    # minimal scope + locked verdict
    (tmp_path / ".omo/_truth/registry").mkdir(parents=True)
    (tmp_path / ".omo/_truth/registry/phase-scope.yaml").write_text(
        """
version: 1
escape_dir: .omo/_delivery/phase-escape
phases:
  phase2:
    id: phase2
    name: delivery
    unlock: {verdict_key: phases.phase2.unlocked, equals: true}
    paths: ["bin/delivery/**"]
""",
        encoding="utf-8",
    )
    (tmp_path / ".omo/_truth/registry/phase-verdict.yaml").write_text(
        """
version: 1
phases:
  phase2:
    unlocked: false
""",
        encoding="utf-8",
    )
    r = mod.check_phases(tmp_path, ["bin/delivery/scheduler.py"])
    assert r["ok"] is False
    assert r["blocks"]
    assert r["blocks"][0]["phase"] == "phase2"


def test_allows_when_unlocked(tmp_path: Path):
    mod = _load()
    (tmp_path / ".omo/_truth/registry").mkdir(parents=True)
    (tmp_path / ".omo/_truth/registry/phase-scope.yaml").write_text(
        """
version: 1
phases:
  phase2:
    id: phase2
    unlock: {verdict_key: phases.phase2.unlocked, equals: true}
    paths: ["bin/delivery/**"]
""",
        encoding="utf-8",
    )
    (tmp_path / ".omo/_truth/registry/phase-verdict.yaml").write_text(
        """
phases:
  phase2: {unlocked: true}
""",
        encoding="utf-8",
    )
    r = mod.check_phases(tmp_path, ["bin/delivery/x.py"])
    assert r["ok"] is True


def test_escape_allows_locked_phase(tmp_path: Path):
    mod = _load()
    (tmp_path / ".omo/_truth/registry").mkdir(parents=True)
    (tmp_path / ".omo/_delivery/phase-escape").mkdir(parents=True)
    (tmp_path / ".omo/_truth/registry/phase-scope.yaml").write_text(
        """
version: 1
escape_dir: .omo/_delivery/phase-escape
phases:
  phase2:
    id: phase2
    unlock: {verdict_key: phases.phase2.unlocked, equals: true}
    paths: ["bin/delivery/**"]
""",
        encoding="utf-8",
    )
    (tmp_path / ".omo/_truth/registry/phase-verdict.yaml").write_text(
        "phases:\n  phase2: {unlocked: false}\n",
        encoding="utf-8",
    )
    (tmp_path / ".omo/_delivery/phase-escape/hot.json").write_text(
        json.dumps(
            {
                "id": "hot-escape",
                "phase": "phase2",
                "pr_number": "999",
                "reason": "test",
                "active": True,
            }
        ),
        encoding="utf-8",
    )
    r = mod.check_phases(
        tmp_path,
        ["bin/delivery/x.py"],
        escape_id="hot-escape",
        pr="999",
    )
    assert r["ok"] is True
    assert r["allowed"][0]["reason"] == "escape"


def test_unrelated_paths_allowed_when_locked(tmp_path: Path):
    mod = _load()
    (tmp_path / ".omo/_truth/registry").mkdir(parents=True)
    (tmp_path / ".omo/_truth/registry/phase-scope.yaml").write_text(
        """
phases:
  phase2:
    id: phase2
    unlock: {verdict_key: phases.phase2.unlocked, equals: true}
    paths: ["bin/delivery/**"]
""",
        encoding="utf-8",
    )
    (tmp_path / ".omo/_truth/registry/phase-verdict.yaml").write_text(
        "phases:\n  phase2: {unlocked: false}\n",
        encoding="utf-8",
    )
    r = mod.check_phases(tmp_path, ["README.md", "docs/OTHER.md"])
    assert r["ok"] is True
