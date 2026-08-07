import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "bin" / "gac" / "check-submodule-rewind.py"


def run_check(args: list[str] | None = None) -> subprocess.CompletedProcess:
    cmd = [sys.executable, str(SCRIPT)]
    if args:
        cmd.extend(args)
    return subprocess.run(cmd, capture_output=True, text=True, cwd=REPO_ROOT)


class TestBasicFunctionality:
    def test_current_main_passes(self):
        result = run_check()
        assert result.returncode == 0
        assert "OK" in result.stdout

    def test_json_output(self):
        result = run_check(["--json"])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["ok"] is True
        assert data["violations"] == []

    def test_verbose_output(self):
        result = run_check(["--verbose"])
        assert result.returncode == 0
        assert "OK" in result.stdout

    def test_json_schema(self):
        result = run_check(["--json"])
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "ok" in data
        assert "violations" in data
        assert "details" in data
        assert isinstance(data["violations"], list)
        assert isinstance(data["details"], list)
