"""测试 check-stale-branches.py"""

import importlib.util
import json
import subprocess
import sys
import time
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent.parent / "bin" / "gac" / "check-stale-branches.py"


def load_module():
    spec = importlib.util.spec_from_file_location(
        "check_stale_branches", str(SCRIPT))
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


class TestListBranches:
    def test_lists_branches(self, tmp_path):
        setup_git(tmp_path)
        (tmp_path / "file.txt").write_text("hello")
        subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "commit", "-m", "init"],
                       cwd=tmp_path, capture_output=True)
        mod = load_module()
        branches = mod.list_branches(tmp_path)
        assert len(branches) >= 1


class TestRunChecks:
    def test_no_stale(self, tmp_path):
        setup_git(tmp_path)
        (tmp_path / "file.txt").write_text("hello")
        subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "commit", "-m", "init"],
                       cwd=tmp_path, capture_output=True)
        mod = load_module()
        results = mod.run_checks(tmp_path, 30, {"main", "master", "develop"}, "HEAD")
        assert results["stale_count"] == 0

    def test_find_merged_branch(self, tmp_path):
        setup_git(tmp_path)
        (tmp_path / "file.txt").write_text("hello")
        subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "commit", "-m", "init"],
                       cwd=tmp_path, capture_output=True)
        # Get actual default branch name BEFORE creating feature
        default_branch = subprocess.run(
            ["git", "symbolic-ref", "--short", "HEAD"],
            capture_output=True, text=True, cwd=tmp_path,
        ).stdout.strip()
        subprocess.run(["git", "checkout", "-b", "feature"],
                       cwd=tmp_path, capture_output=True)
        (tmp_path / "feature.txt").write_text("feature")
        subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "commit", "-m", "feature work"],
                       cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "checkout", default_branch],
                       cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "merge", "feature"],
                       cwd=tmp_path, capture_output=True)
        mod = load_module()
        results = mod.run_checks(
            tmp_path, 30, {default_branch, "main", "master"}, default_branch)
        assert results["merged_count"] >= 1


class TestCLI:
    def test_json_output(self, tmp_path):
        setup_git(tmp_path)
        (tmp_path / "file.txt").write_text("hello")
        subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "commit", "-m", "init"],
                       cwd=tmp_path, capture_output=True)
        result = run_script("--json", workspace=tmp_path)
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "total_branches" in data
        assert "stale_count" in data
        assert "merged_count" in data

    def test_custom_ttl(self, tmp_path):
        setup_git(tmp_path)
        (tmp_path / "file.txt").write_text("hello")
        subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "commit", "-m", "init"],
                       cwd=tmp_path, capture_output=True)
        result = run_script("--json", "--ttl-days", "1", workspace=tmp_path)
        assert result.returncode == 0

    def test_custom_protected(self, tmp_path):
        setup_git(tmp_path)
        (tmp_path / "file.txt").write_text("hello")
        subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "commit", "-m", "init"],
                       cwd=tmp_path, capture_output=True)
        result = run_script("--json", "--protected-branches", "main",
                           workspace=tmp_path)
        assert result.returncode == 0
