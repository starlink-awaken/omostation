"""测试 check-diff-lifecycle.py — BET-Y1Q4-T10-145"""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent.parent / "bin" / "gac" / "check-diff-lifecycle.py"


def load_module():
    spec = importlib.util.spec_from_file_location(
        "check_diff_lifecycle", str(SCRIPT))
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


class TestFindPatchFiles:
    def test_no_patch_files(self, tmp_path):
        setup_git(tmp_path)
        (tmp_path / "file.txt").write_text("hello")
        subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "commit", "-m", "init"],
                       cwd=tmp_path, capture_output=True)
        mod = load_module()
        files = mod.find_patch_files(tmp_path, "HEAD")
        assert files == []


class TestParsePatchCommits:
    def test_parse_valid_patch(self, tmp_path):
        patch_content = """commit abc1234567890abcdef1234567890abcdef123
Author: Test User <test@example.com>
Subject: Add test file

diff --git a/test.py b/test.py
new file mode 100644
index 0000000..1234567
--- /dev/null
+++ b/test.py

commit def456789012345678901234567890abcdef12
Author: Another User <another@example.com>
Subject: Fix bug

diff --git a/fix.py b/fix.py
new file mode 100644
index 0000000..6789012
--- /dev/null
+++ b/fix.py
"""
        patch_file = tmp_path / "test.patch"
        patch_file.write_text(patch_content)
        mod = load_module()
        commits = mod.parse_patch_commits(patch_file)
        assert len(commits) == 2
        assert commits[0]["sha"] == "abc1234567890abcdef1234567890abcdef123"
        assert "Add test file" in commits[0]["subject"]
        assert "a/test.py" in commits[0]["files_modified"]

    def test_parse_empty_patch(self, tmp_path):
        patch_file = tmp_path / "empty.patch"
        patch_file.write_text("")
        mod = load_module()
        commits = mod.parse_patch_commits(patch_file)
        assert commits == []

    def test_parse_single_commit(self, tmp_path):
        patch_content = """commit 1111111111111111111111111111111111111111
Author: Dev <dev@example.com>
Subject: Initial commit

diff --git a/main.py b/main.py
new file mode 100644
index 0000000..abcdef1
--- /dev/null
+++ b/main.py
"""
        patch_file = tmp_path / "single.patch"
        patch_file.write_text(patch_content)
        mod = load_module()
        commits = mod.parse_patch_commits(patch_file)
        assert len(commits) == 1
        assert commits[0]["sha"] == "1111111111111111111111111111111111111111"


class TestCheckCommitApplied:
    def test_commit_in_history(self, tmp_path):
        setup_git(tmp_path)
        (tmp_path / "file1.txt").write_text("hello")
        subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "commit", "-m", "first"],
                       cwd=tmp_path, capture_output=True)
        sha = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, cwd=tmp_path,
        ).stdout.strip()
        (tmp_path / "file2.txt").write_text("world")
        subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "commit", "-m", "second"],
                       cwd=tmp_path, capture_output=True)
        mod = load_module()
        assert mod.check_commit_applied(tmp_path, sha) is True

    def test_commit_not_in_history(self, tmp_path):
        setup_git(tmp_path)
        (tmp_path / "file.txt").write_text("hello")
        subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "commit", "-m", "first"],
                       cwd=tmp_path, capture_output=True)
        mod = load_module()
        assert mod.check_commit_applied(
            tmp_path, "deadbeefdeadbeefdeadbeefdeadbeefdeadbeef") is False


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
        assert "total_patch_files" in data
        assert "blocking" in data
        assert "warnings" in data

    def test_no_git_repo(self, tmp_path):
        non_repo = tmp_path / "non-repo"
        non_repo.mkdir()
        result = run_script("--workspace", str(non_repo))
        assert result.returncode != 0

    def test_fail_on_blocking_flag(self, tmp_path):
        setup_git(tmp_path)
        (tmp_path / "file.txt").write_text("hello")
        subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "commit", "-m", "init"],
                       cwd=tmp_path, capture_output=True)
        result = run_script("--fail-on-blocking", workspace=tmp_path)
        assert result.returncode == 0
