"""Basic tests for Forge tool registry and discovery."""

import shutil
import subprocess
from pathlib import Path

import pytest

# Locate forge CLI - check PATH first, then fallback to venv
_FORGE_PATH = shutil.which("forge") or shutil.which("forge-bridge")
if not _FORGE_PATH:
    # Fallback to venv bin
    _VENV_FORGE = Path(__file__).resolve().parents[3] / ".venv" / "bin" / "forge"
    if _VENV_FORGE.exists():
        _FORGE_PATH = str(_VENV_FORGE)

FORGE = _FORGE_PATH


def _run_cli(*args: str) -> tuple[int, str]:
    proc = subprocess.run(
        [FORGE, *args],  # type: ignore[list-item]
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.returncode, proc.stdout or proc.stderr


class TestForgeBasic:
    @pytest.mark.skipif(not FORGE, reason="forge CLI not found on PATH")
    def test_forge_help(self):
        rc, out = _run_cli("--help")
        assert rc == 0

    @pytest.mark.skipif(not FORGE, reason="forge CLI not found on PATH")
    def test_forge_status(self):
        rc, out = _run_cli("status")
        assert rc in (0, 1)  # 1 if no backend available

    @pytest.mark.skipif(not FORGE, reason="forge CLI not found on PATH")
    def test_forge_list(self):
        rc, out = _run_cli("list")
        assert rc == 0
