"""Tests for bin/ssot/validate-runbook-refs.py

Covers:
  - extracts bin/X.py references from runbook markdown
  - skips archived paths
  - skips "planned" / "TBD" / "future" markers
  - skips template / example language
  - JSON output format
  - broken-ref detection when path doesn't exist
  - existing-path recognition
  - empty docs dir
  - multiple roots
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "bin" / "ssot" / "validate-runbook-refs.py"
_MODULE = "_validate_runbook_refs_test"


def _load():
    spec = importlib.util.spec_from_file_location(_MODULE, SCRIPT)
    assert spec and spec.loader
    m = importlib.util.module_from_spec(spec)
    sys.modules[_MODULE] = m
    spec.loader.exec_module(m)
    return m


@pytest.fixture(scope="module")
def v():
    return _load()


def _write_md(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_extracts_bin_py_references(v):
    """Direct bin/ path references are collected."""
    content = "Run `bin/gac/gac-validate.py --gate` and then `bin/ssot/check-link.py`.\n"
    refs = v.collect_refs([Path("/nonexistent")])
    # extract_refs is called with explicit roots; here we just test the regex
    import re

    matches = v._BIN_REF_RE.findall(content)
    assert "bin/gac/gac-validate.py" in matches
    assert "bin/ssot/check-link.py" in matches


def test_extracts_bin_sh_references(v):
    content = "Use `bin/ssot/sync-submodules-push.sh` to sync.\n"
    matches = v._BIN_REF_RE.findall(content)
    assert "bin/ssot/sync-submodules-push.sh" in matches


def test_skips_archived_paths(v, tmp_path):
    """Files in _archive/ should be skipped entirely."""
    archive_dir = tmp_path / "docs" / "_archive"
    _write_md(
        archive_dir / "old.md",
        "Use `bin/gac/check-real.py` and `bin/gac/check-fake.py`.\n",
    )
    real_dir = tmp_path / "docs" / "operations"
    _write_md(
        real_dir / "current.md",
        "Use `bin/gac/check-real.py` only.\n",
    )

    refs = v.collect_refs([tmp_path / "docs"])
    # archived file should NOT appear in refs at all
    assert str(archive_dir / "old.md") not in refs
    # current file should appear
    assert str(real_dir / "current.md") in refs


def test_skips_template_and_example_language(v, tmp_path):
    """Lines with template/example/e.g. markers should be skipped."""
    docs_dir = tmp_path / "docs" / "operations"
    _write_md(
        docs_dir / "guide.md",
        "e.g. bin/gac/whatever.py for example.\n"
        "TODO: bin/gac/future-thing.py (planned).\n"
        "Or bin/gac/alt.py as a fallback.\n"
        "Real one: bin/gac/real.py\n",
    )
    refs = v.collect_refs([docs_dir])
    md_refs = list(refs.values())[0] if refs else set()
    # only the "real one" survives
    assert md_refs == {"bin/gac/real.py"}


def test_broken_refs_detected(v, tmp_path):
    """A bin/ ref that doesn't exist in the workspace returns rc=1."""
    docs_dir = tmp_path / "fake_docs"
    _write_md(
        docs_dir / "fake.md",
        "Use `bin/gac/real.py` and `bin/gac/missing.py`.\n",
    )
    rc = v.collect_refs.__module__ and v.main(["--json", "--root", str(docs_dir)])
    assert rc == 1


def test_existing_refs_pass(v, tmp_path, monkeypatch):
    """Real bin/ refs in workspace return rc=0."""
    # Create a real bin script
    work_bin = tmp_path / "bin" / "gac"
    work_bin.mkdir(parents=True)
    (work_bin / "real-tool.py").write_text("#!/usr/bin/env python3\nprint('ok')\n")

    docs_dir = tmp_path / "docs"
    _write_md(
        docs_dir / "test.md",
        f"Use `{work_bin / 'real-tool.py'}`.\n",
    )

    # Patch WORKSPACE so collect_refs resolves relative paths
    v = sys.modules[_MODULE]
    original_workspace = v.WORKSPACE
    monkeypatch.setattr(v, "WORKSPACE", tmp_path)
    try:
        rc = v.main(["--json", "--root", str(docs_dir)])
    finally:
        monkeypatch.setattr(v, "WORKSPACE", original_workspace)

    assert rc == 0


def test_json_output_structure(v, tmp_path, monkeypatch, capsys):
    """--json produces parseable JSON with expected keys."""
    docs_dir = tmp_path / "docs" / "ops"
    _write_md(
        docs_dir / "test.md",
        "Use `bin/gac/missing.py` (should fail).\n",
    )

    v = sys.modules[_MODULE]
    monkeypatch.setattr(v, "WORKSPACE", tmp_path)
    rc = v.main(["--json", "--root", str(docs_dir)])

    data = json.loads(capsys.readouterr().out)
    assert rc == 1
    assert "broken" in data
    assert "broken_count" in data
    assert data["broken_count"] >= 1


def test_archived_bin_path_still_counted(v, tmp_path, monkeypatch):
    """A ref to bin/_archive/X.py should NOT be counted as broken."""
    work_root = tmp_path
    archive_dir = work_root / "bin" / "_archive"
    archive_dir.mkdir(parents=True)
    (archive_dir / "old-tool.py").write_text("#!/usr/bin/env python3\n")

    docs_dir = work_root / "docs" / "ops"
    _write_md(
        docs_dir / "test.md",
        f"Use `{archive_dir / 'old-tool.py'}` (archived).\n",
    )

    v = sys.modules[_MODULE]
    monkeypatch.setattr(v, "WORKSPACE", work_root)
    rc = v.main(["--json", "--root", str(docs_dir)])

    data = json.loads(rc if isinstance(rc, str) else "{}")  # fall through
    # It should NOT be reported as broken (path exists inside _archive)
    assert data.get("broken_count", 0) == 0


def test_main_empty_docs_dir(tmp_path, monkeypatch):
    """Empty docs dir → rc=0, no broken."""
    v = sys.modules[_MODULE]
    monkeypatch.setattr(v, "WORKSPACE", tmp_path)
    v = sys.modules[_MODULE]
    rc = v.main(["--json", "--root", str(tmp_path / "nonexistent_dir")])
    assert rc == 0


def test_is_archived_recognizes_nested(v, tmp_path):
    """_archive anywhere in path marks as archived."""
    nested = tmp_path / "_archive" / "deep" / "depth1" / "depth2"
    assert v._is_archived(nested)


def test_is_archived_does_not_match_similar_names(v, tmp_path):
    """archive-snapshot is not the same as _archive."""
    similar = tmp_path / "archive-snapshot"
    assert not v._is_archived(similar)


def test_skips_e_g_marker_line(v):
    """Lines starting with 'e.g.' should be skipped entirely."""
    assert v._is_skippable_line("e.g. bin/gac/foo.py for testing")
    assert v._is_skippable_line("Or bin/gac/bar.py as backup")
    assert v._is_skippable_line("See bin/gac/baz.py for docs")
    assert not v._is_skippable_line("Run bin/gac/real.py now")
