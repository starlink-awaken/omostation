"""kairon-cli compatibility tests for KOS search exposure."""

from __future__ import annotations

import subprocess
import sys
import tomllib
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent.parent
CLI_PATH = SCRIPT_DIR / "kairon-cli.py"
PYPROJECT_PATH = SCRIPT_DIR / "pyproject.toml"


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(CLI_PATH), *args],
        capture_output=True,
        text=True,
        timeout=30,
        cwd=str(SCRIPT_DIR),
    )


def test_kairon_cli_wrapper_exposes_search_help() -> None:
    result = _run("search", "--help")

    assert result.returncode == 0


def test_kairon_cli_wrapper_accepts_search_invocation() -> None:
    result = _run("search", "test", "--format", "table", "--limit", "2")

    assert result.returncode in (0, 1)


def test_pyproject_exposes_kairon_cli_entrypoint() -> None:
    pyproject = tomllib.loads(PYPROJECT_PATH.read_text(encoding="utf-8"))

    assert pyproject["project"]["scripts"]["kairon-cli"] == "kos.cli.__main__:main"
