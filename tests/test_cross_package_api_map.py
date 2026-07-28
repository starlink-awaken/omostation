"""Tests for the cross-package API map generator."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

# Load the script as a module under the name `bin.cross_package_api_map`
# so the test suite can use ordinary import syntax without forcing a
# `__init__.py` into the bin/ package (which would interfere with the
# way the bin/ scripts are dispatched in production).
_MODULE_NAME = "bin.cross_package_api_map"
_SPEC = importlib.util.spec_from_file_location(
    _MODULE_NAME, Path(__file__).resolve().parent.parent / "bin" / "cross_package_api_map.py"
)
_module = importlib.util.module_from_spec(_SPEC)
sys.modules[_MODULE_NAME] = _module
_SPEC.loader.exec_module(_module)
# Convenience aliases used by the tests below.
_module_to_package = _module._module_to_package
_kairon_workspace_members = _module._kairon_workspace_members
PYTHON_DASH_M_RE = _module.PYTHON_DASH_M_RE
main = _module.main

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "bin"


def test_module_to_package_handles_nested_modules():
    from bin.cross_package_api_map import _module_to_package

    workspace = {"ontoderive", "minerva", "eidos", "codeanalyze"}
    assert _module_to_package("ontoderive.mcp_server", workspace) == "ontoderive"
    assert _module_to_package("minerva.pipeline.engine", workspace) == "minerva"
    assert _module_to_package("eidos.cli", workspace) == "eidos"
    assert _module_to_package("codeanalyze", workspace) == "codeanalyze"
    assert _module_to_package("agora.mcp.bos_resolver", workspace) is None
    assert _module_to_package("totally_unknown", workspace) is None


def test_kairon_workspace_members_reads_packages_directory(tmp_path: Path):
    from bin.cross_package_api_map import _kairon_workspace_members

    (tmp_path / "packages").mkdir()
    for name in ("alpha", "beta", "gamma"):
        pkg = tmp_path / "packages" / name
        pkg.mkdir()
        (pkg / "pyproject.toml").write_text("[project]\nname='x'\n")
    # Sub-directory without pyproject.toml should be excluded.
    (tmp_path / "packages" / "scratch").mkdir()
    (tmp_path / "pyproject.toml").write_text(
        '[tool.uv.workspace]\nmembers = ["packages/*"]\n'
    )
    members = _kairon_workspace_members(tmp_path)
    assert members == {"alpha", "beta", "gamma"}


def test_python_dash_m_regex_matches_module_names():
    from bin.cross_package_api_map import PYTHON_DASH_M_RE

    cases = {
        "uv run python -m ontoderive.mcp_server": "ontoderive.mcp_server",
        "python3 -m eidos.cli validate": "eidos.cli",
        "uv run --directory projects/kairon python -m minerva.mcp_server.server": "minerva.mcp_server.server",
        "uv run bun run cli.ts": None,
        "uv run --directory projects/kairon codeanalyze serve": None,
    }
    for cmd, expected in cases.items():
        match = PYTHON_DASH_M_RE.search(cmd)
        assert (match.group("module") if match else None) == expected, cmd


def test_main_writes_markdown_table(tmp_path: Path):
    from bin.cross_package_api_map import main

    out = tmp_path / "map.md"
    rc = main(
        [
            "--bos-registry",
            str(REPO_ROOT / "projects" / "agora" / "etc" / "bos-services.yaml"),
            "--kairon-root",
            str(REPO_ROOT / "projects" / "kairon"),
            "--out",
            str(out),
        ]
    )
    assert rc == 0
    text = out.read_text(encoding="utf-8")
    assert text.startswith("# Cross-Package API Map")
    # Every row of the table starts with a pipe and a kairon package.
    table_rows = [
        line
        for line in text.splitlines()
        if line.startswith("| ") and "---" not in line
    ]
    # The header is the first row after the separator.
    assert table_rows[0].startswith("| Kairon package")
    assert any("ontoderive" in row for row in table_rows)
    assert any("minerva" in row for row in table_rows)
    # Section for packages without any route.
    assert "Kairon packages without any BOS route" in text


def test_main_missing_registry(tmp_path: Path, capsys):
    from bin.cross_package_api_map import main

    rc = main(["--bos-registry", str(tmp_path / "nope.yaml"), "--out", str(tmp_path / "out.md")])
    assert rc == 1
    err = capsys.readouterr().err
    assert "bos registry not found" in err


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
