"""Regression tests for the tracked-workspace hygiene gate."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

_MODULE_PATH = Path(__file__).resolve().parents[3] / "bin" / "gac" / "gac-hygiene-check.py"
_SPEC = importlib.util.spec_from_file_location("gac_hygiene_check", _MODULE_PATH)
assert _SPEC and _SPEC.loader
hygiene = importlib.util.module_from_spec(_SPEC)
sys.modules["gac_hygiene_check"] = hygiene
_SPEC.loader.exec_module(hygiene)


def _empty(root: Path, relative: str) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch()
    return path


@pytest.mark.parametrize("marker", ["pkg/__init__.py", "pkg/py.typed", "pkg/.gitkeep"])
def test_legal_empty_markers_are_not_hygiene_findings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, marker: str
) -> None:
    monkeypatch.setattr(hygiene, "WORKSPACE_ROOT", tmp_path)
    _empty(tmp_path, marker)

    assert hygiene.find_zero_byte_files({marker}) == []


def test_gbrain_test_outputs_are_an_exact_path_contract(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(hygiene, "WORKSPACE_ROOT", tmp_path)
    allowed = "projects/knowledge/gbrain/.context/test-failures.log"
    other = "projects/knowledge/gbrain/.context/unrelated-empty.log"
    _empty(tmp_path, allowed)
    _empty(tmp_path, other)

    assert hygiene.find_zero_byte_files({allowed, other}) == [tmp_path / other]


def test_empty_non_marker_is_a_hygiene_finding(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(hygiene, "WORKSPACE_ROOT", tmp_path)
    path = "src/accidental-empty.py"
    _empty(tmp_path, path)

    assert hygiene.find_zero_byte_files({path}) == [tmp_path / path]


def test_missing_tracked_path_is_reported_instead_of_silently_skipped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(hygiene, "WORKSPACE_ROOT", tmp_path)

    assert hygiene.find_missing_tracked_files({"src/missing.py"}) == [tmp_path / "src/missing.py"]


def test_existing_tracked_directory_symlink_is_not_a_missing_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(hygiene, "WORKSPACE_ROOT", tmp_path)
    (tmp_path / "truth").mkdir()
    (tmp_path / "links").mkdir()
    (tmp_path / "links" / "truth").symlink_to(tmp_path / "truth", target_is_directory=True)

    assert hygiene.find_missing_tracked_files({"links/truth"}) == []


def test_tracked_file_listing_excludes_gitlinks_without_quoting_unicode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Keep the NUL-delimited fixture split: collapsing adjacent literals would
    # make `\0` consume the following octal-looking path prefix.
    # fmt: off
    output = (
        "100644 deadbeef 0\tplain.txt\0"
        "160000 deadbeef 0\tprojects/submodule\0"
        "100644 deadbeef 0\tdocs/中文.md\0"
    )
    # fmt: on

    def fake_run(*args: object, **kwargs: object) -> SimpleNamespace:
        assert args[0] == ["git", "ls-files", "--stage", "-z"]
        return SimpleNamespace(returncode=0, stdout=output)

    monkeypatch.setattr(subprocess, "run", fake_run)

    assert hygiene.git_tracked_files() == {"plain.txt", "docs/中文.md"}
