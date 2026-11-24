"""Tests aligning scoped_doc_link_command with doc-link-check LOCAL_DOC_GLOBS."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "bin" / "gac" / "gac-local-gate.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("gac_local_gate_doclink_probe", SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_matches_doc_link_surface_rejects_nested_docs_readme_and_pitfalls() -> None:
    mod = _load_module()
    assert mod._matches_doc_link_surface("AGENTS.md") is True
    assert mod._matches_doc_link_surface("README.md") is True
    assert mod._matches_doc_link_surface("projects/AGENTS.md") is True
    assert mod._matches_doc_link_surface("projects/omo/AGENTS.md") is True
    assert mod._matches_doc_link_surface("projects/omo/CLAUDE.md") is True
    assert mod._matches_doc_link_surface("projects/omo/README.md") is False

    # Regression guard: PurePosixPath("docs/README.md").match("README.md") is True in stdlib!
    assert mod._matches_doc_link_surface("docs/README.md") is False
    assert mod._matches_doc_link_surface("docs/pitfalls.md") is False
    assert mod._matches_doc_link_surface(".omo/debt/README.md") is False
    assert mod._matches_doc_link_surface("projects/knowledge/gbrain/README.md") is False


def test_scoped_doc_link_command_filters_staged_md_to_declared_surface(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mod = _load_module()
    monkeypatch.setattr(
        mod,
        "staged_files_git",
        lambda: ["docs/pitfalls.md", "docs/README.md", "AGENTS.md", "projects/omo/AGENTS.md"],
    )

    assert mod.scoped_doc_link_command("staged", None, "", False) == [
        "bin/ssot/doc-link-check.py",
        "--files",
        "AGENTS.md",
        "projects/omo/AGENTS.md",
    ]


def test_scoped_doc_link_command_skips_when_only_non_surface_docs_staged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mod = _load_module()
    monkeypatch.setattr(
        mod,
        "staged_files_git",
        lambda: ["docs/pitfalls.md", "docs/plans/foo.md", ".omo/notes.md"],
    )
    assert mod.scoped_doc_link_command("staged", None, "", False) is None


def test_scoped_doc_link_command_respects_files_scope_and_strict_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mod = _load_module()
    monkeypatch.setattr(mod, "staged_files_git", lambda: ["README.md"])

    assert mod.scoped_doc_link_command("files", ["docs/pitfalls.md"], "", False) is None
    assert mod.scoped_doc_link_command("files", ["docs/pitfalls.md", "CLAUDE.md"], "", False) == [
        "bin/ssot/doc-link-check.py",
        "--files",
        "CLAUDE.md",
    ]
    assert mod.scoped_doc_link_command("staged", None, "", True) == ["bin/ssot/doc-link-check.py"]
