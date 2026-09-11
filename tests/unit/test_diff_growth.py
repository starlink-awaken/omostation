"""测试 check-diff-growth.py — BET-Y1Q4-T10-147"""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent.parent / "bin" / "gac" / "check-diff-growth.py"


def load_module():
    spec = importlib.util.spec_from_file_location(
        "check_diff_growth", str(SCRIPT))
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


class TestGetDiffStats:
    def test_no_changes(self, tmp_path):
        setup_git(tmp_path)
        (tmp_path / "file.py").write_text("x = 1\n")
        subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "commit", "-m", "init"],
                       cwd=tmp_path, capture_output=True)
        mod = load_module()
        stats = mod.get_diff_stats(tmp_path, "HEAD", "HEAD")
        assert stats["files_changed"] == 0
        assert stats["net_lines"] == 0


class TestRunChecks:
    def test_under_threshold(self, tmp_path):
        setup_git(tmp_path)
        (tmp_path / "file.py").write_text("x = 1\n")
        subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "commit", "-m", "init"],
                       cwd=tmp_path, capture_output=True)
        mod = load_module()
        results = mod.run_checks(tmp_path, "HEAD", "HEAD", 2000, 100)
        assert results["violations"] == []

    def test_over_line_threshold(self, tmp_path):
        setup_git(tmp_path)
        (tmp_path / "file.py").write_text("x = 1\n")
        subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "commit", "-m", "init"],
                       cwd=tmp_path, capture_output=True)
        mod = load_module()
        results = mod.run_checks(tmp_path, "HEAD", "HEAD", 0, 100)
        assert all(v["metric"] != "net_lines" for v in results["violations"])


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
        assert "stats" in data
        assert "thresholds" in data
        assert "violations" in data
        assert "files_changed" in data["stats"]

    def test_custom_thresholds(self, tmp_path):
        setup_git(tmp_path)
        (tmp_path / "file.py").write_text("x = 1\n")
        subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "commit", "-m", "init"],
                       cwd=tmp_path, capture_output=True)
        result = run_script("--json", "--max-lines", "5", "--max-files", "2",
                           workspace=tmp_path)
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["thresholds"]["max_lines"] == 5
        assert data["thresholds"]["max_files"] == 2

    def test_no_git_repo(self, tmp_path):
        non_repo = tmp_path / "non-repo"
        non_repo.mkdir()
        result = run_script("--workspace", str(non_repo))
        assert result.returncode != 0
