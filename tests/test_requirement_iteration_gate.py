"""Unit tests for ADR-0204 requirement_iteration_report (staged-only hard gate)."""
from __future__ import annotations

import os
from pathlib import Path
from unittest import mock

import pytest

# Resolve omo from workspace submodule
ROOT = Path(__file__).resolve().parents[1]
import sys

sys.path.insert(0, str(ROOT / "projects" / "omo" / "src"))

from omo.workflow import diagnostics as diag  # noqa: E402


POLICY = {
    "mode": "required",
    "adr": "ADR-0203",
    "in_scope_paths": ["docs/**", "bin/**"],
    "exclude_paths": [".omo/state/**"],
}


def test_no_changes_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AGCP_REQUIREMENT_ITERATION_GATE", raising=False)
    monkeypatch.setattr(diag, "staged_files_from_git", lambda: [])
    monkeypatch.setattr(diag, "changed_files_from_git", lambda include_untracked=False: [])
    monkeypatch.setattr(diag, "load_run_records", lambda registry: {})
    report = diag.requirement_iteration_report({"requirement_iteration_policy": POLICY})
    assert report["ok"] is True
    assert report["checked"] is True
    assert report["findings"] == []


def test_staged_without_active_run_halts(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AGCP_REQUIREMENT_ITERATION_GATE", raising=False)
    monkeypatch.setattr(
        diag, "staged_files_from_git", lambda: ["docs/closeout/foo.md"]
    )
    monkeypatch.setattr(diag, "changed_files_from_git", lambda include_untracked=False: [])
    monkeypatch.setattr(diag, "load_run_records", lambda registry: {})
    report = diag.requirement_iteration_report({"requirement_iteration_policy": POLICY})
    assert report["ok"] is False
    kinds = {f["kind"] for f in report["findings"]}
    assert "requirement_iteration_no_active_run" in kinds
    assert any(f["severity"] == "halt" for f in report["findings"])


def test_staged_with_active_run_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AGCP_REQUIREMENT_ITERATION_GATE", raising=False)
    monkeypatch.setattr(
        diag, "staged_files_from_git", lambda: ["docs/closeout/foo.md"]
    )
    monkeypatch.setattr(diag, "changed_files_from_git", lambda include_untracked=False: [])
    monkeypatch.setattr(
        diag,
        "load_run_records",
        lambda registry: {
            "run-1": (Path("x"), {"status": "active"}),
        },
    )
    report = diag.requirement_iteration_report({"requirement_iteration_policy": POLICY})
    assert report["ok"] is True
    assert report["active_runs"] == ["run-1"]


def test_unstaged_only_warns(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AGCP_REQUIREMENT_ITERATION_GATE", raising=False)
    monkeypatch.setattr(diag, "staged_files_from_git", lambda: [])
    monkeypatch.setattr(
        diag,
        "changed_files_from_git",
        lambda include_untracked=False: ["docs/closeout/foo.md"],
    )
    monkeypatch.setattr(diag, "load_run_records", lambda registry: {})
    report = diag.requirement_iteration_report({"requirement_iteration_policy": POLICY})
    assert report["ok"] is True  # warn only
    assert any(
        f["kind"] == "requirement_iteration_dirty_without_run"
        for f in report["findings"]
    )


def test_bypass_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGCP_REQUIREMENT_ITERATION_GATE", "0")
    monkeypatch.setattr(
        diag, "staged_files_from_git", lambda: ["docs/closeout/foo.md"]
    )
    monkeypatch.setattr(diag, "changed_files_from_git", lambda include_untracked=False: [])
    monkeypatch.setattr(diag, "load_run_records", lambda registry: {})
    report = diag.requirement_iteration_report({"requirement_iteration_policy": POLICY})
    assert report["ok"] is True
    assert report.get("bypassed") is True
