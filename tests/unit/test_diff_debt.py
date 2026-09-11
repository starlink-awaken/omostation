"""测试 check-diff-debt.py — BET-Y1Q4-T10-146"""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent.parent / "bin" / "gac" / "check-diff-debt.py"


def load_module():
    spec = importlib.util.spec_from_file_location(
        "check_diff_debt", str(SCRIPT))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run_script(*args, workspace=None):
    cmd = [sys.executable, str(SCRIPT)]
    if workspace:
        cmd += ["--workspace", str(workspace)]
    cmd += list(args)
    return subprocess.run(cmd, capture_output=True, text=True)


def setup_git(workspace):
    subprocess.run(["git", "init", str(workspace)], check=True,
                   capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"],
                   cwd=workspace, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"],
                   cwd=workspace, capture_output=True)


class TestScanDebtMarkers:
    def test_find_todos(self, tmp_path):
        setup_git(tmp_path)
        (tmp_path / "file.py").write_text("# Initial\n")
        subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "commit", "-m", "init"],
                       cwd=tmp_path, capture_output=True)
        (tmp_path / "file.py").write_text(
            "# Initial\ndef foo():\n    # TODO: fix this later\n    pass\n")
        subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "commit", "-m", "add TODO"],
                       cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "commit", "-m", "add TODO"],
                       cwd=tmp_path, capture_output=True)
        mod = load_module()
        debts = mod.scan_debt_markers(tmp_path, "file.py", "HEAD~1", "HEAD")
        markers = [d["marker"] for d in debts]
        assert "TODO" in markers


class TestCheckDebtInBase:
    def test_debt_in_base(self, tmp_path):
        setup_git(tmp_path)
        (tmp_path / "file.py").write_text("# HACK: workaround\nx = 1\n")
        subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "commit", "-m", "init with HACK"],
                       cwd=tmp_path, capture_output=True)
        mod = load_module()
        assert mod.check_debt_in_base(tmp_path, "file.py", "HACK", "HEAD") is True

    def test_debt_not_in_base(self, tmp_path):
        setup_git(tmp_path)
        (tmp_path / "file.py").write_text("x = 1\n")
        subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "commit", "-m", "init"],
                       cwd=tmp_path, capture_output=True)
        mod = load_module()
        assert mod.check_debt_in_base(tmp_path, "file.py", "FIXME", "HEAD") is False


class TestCLI:
    def test_json_output(self, tmp_path):
        setup_git(tmp_path)
        (tmp_path / "file.py").write_text("x = 1\n")
        subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "commit", "-m", "init"],
                       cwd=tmp_path, capture_output=True)
        result = run_script("--json", workspace=tmp_path)
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "total_files_scanned" in data
        assert "total_debt_markers" in data
        assert "existing_debt" in data
        assert "new_debt" in data

    def test_no_git_repo(self, tmp_path):
        non_repo = tmp_path / "non-repo"
        non_repo.mkdir()
        result = run_script("--workspace", str(non_repo))
        assert result.returncode != 0

    def test_empty_diff(self, tmp_path):
        setup_git(tmp_path)
        (tmp_path / "file.py").write_text("x = 1\n")
        subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "commit", "-m", "init"],
                       cwd=tmp_path, capture_output=True)
        result = run_script("--json", workspace=tmp_path)
        assert result.returncode == 0
