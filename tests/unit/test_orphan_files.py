"""测试 check-orphan-files.py"""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent.parent / "bin" / "gac" / "check-orphan-files.py"


def load_module():
    spec = importlib.util.spec_from_file_location(
        "check_orphan_files", str(SCRIPT))
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


class TestScanFiles:
    def test_scan_omo_dir(self, tmp_path):
        setup_git(tmp_path)
        omo_dir = tmp_path / ".omo"
        omo_dir.mkdir()
        (omo_dir / "test.yaml").write_text("key: value")
        (omo_dir / "script.py").write_text("print('hello')")
        mod = load_module()
        files = mod.scan_files(tmp_path, [".omo"])
        assert len(files) == 2
        assert ".omo/test.yaml" in files
        assert ".omo/script.py" in files

    def test_scan_bin_dir(self, tmp_path):
        setup_git(tmp_path)
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        (bin_dir / "test.sh").write_text("#!/bin/bash\necho hello")
        mod = load_module()
        files = mod.scan_files(tmp_path, ["bin"])
        assert len(files) == 1
        assert "bin/test.sh" in files

    def test_scan_nonexistent_dir(self, tmp_path):
        setup_git(tmp_path)
        mod = load_module()
        files = mod.scan_files(tmp_path, ["nonexistent"])
        assert files == []


class TestFindReferences:
    def test_find_referenced_file(self, tmp_path):
        setup_git(tmp_path)
        (tmp_path / "README.md").write_text("See test.py for details")
        (tmp_path / "test.py").write_text("print('hello')")
        subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "commit", "-m", "init"],
                       cwd=tmp_path, capture_output=True)
        mod = load_module()
        refs = mod.find_references(tmp_path, "test.py")
        assert "README.md" in refs


class TestRunChecks:
    def test_no_orphans(self, tmp_path):
        setup_git(tmp_path)
        (tmp_path / "README.md").write_text("See script.py")
        script_dir = tmp_path / "bin"
        script_dir.mkdir()
        (script_dir / "script.py").write_text("print('hello')")
        subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "commit", "-m", "init"],
                       cwd=tmp_path, capture_output=True)
        mod = load_module()
        results = mod.run_checks(tmp_path, ["bin"])
        assert results["orphaned_count"] == 0


class TestCLI:
    def test_json_output(self, tmp_path):
        setup_git(tmp_path)
        (tmp_path / "README.md").write_text("See script.py")
        script_dir = tmp_path / "bin"
        script_dir.mkdir()
        (script_dir / "script.py").write_text("print('hello')")
        subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "commit", "-m", "init"],
                       cwd=tmp_path, capture_output=True)
        result = run_script("--json", workspace=tmp_path)
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "total_files" in data
        assert "referenced" in data
        assert "orphaned_count" in data
        assert "orphaned_files" in data

    def test_custom_dirs(self, tmp_path):
        setup_git(tmp_path)
        custom_dir = tmp_path / "custom"
        custom_dir.mkdir()
        (custom_dir / "file.py").write_text("x = 1")
        subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
        subprocess.run(["git", "commit", "-m", "init"],
                       cwd=tmp_path, capture_output=True)
        result = run_script("--json", "--dirs", "custom", workspace=tmp_path)
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["total_files"] >= 0
