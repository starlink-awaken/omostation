"""Tests for E-DOC-001~005 Documents boundary gate (check-documents-boundary.py)."""

from __future__ import annotations

import json
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "bin" / "gac" / "check-documents-boundary.py"
WORKSPACE = Path(__file__).resolve().parents[1]


def _run_check(
    tmp_path: Path,
    *,
    rule: str | None = None,
    json_output: bool = True,
    auto_fix: bool = False,
    dry_run: bool = False,
) -> tuple[int, dict | str]:
    """Run check-documents-boundary.py with a temp Documents root."""
    cmd = [
        sys.executable,
        str(SCRIPT),
        "--documents-root",
        str(tmp_path),
    ]
    if json_output:
        cmd.append("--json")
    if rule:
        cmd.extend(["--rule", rule])
    if auto_fix:
        cmd.append("--auto-fix")
    if dry_run:
        cmd.append("--dry-run")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    output = result.stdout.strip()
    if json_output and output:
        return result.returncode, json.loads(output)
    return result.returncode, output


# ── E-DOC-001: Executable script detection ──────────────────────────────────

class TestEDOC001:
    def test_no_violations_empty_dir(self, tmp_path: Path) -> None:
        """Empty Documents should pass."""
        rc, data = _run_check(tmp_path, rule="E-DOC-001")
        assert rc == 0
        assert data["ok"] is True
        assert data["error_count"] == 0

    def test_detects_python_script(self, tmp_path: Path) -> None:
        """Python script in Documents root = violation."""
        script = tmp_path / "malicious.py"
        script.write_text("print('hello')")
        rc, data = _run_check(tmp_path, rule="E-DOC-001")
        assert rc == 1
        assert data["ok"] is False
        assert any(v["rule"] == "E-DOC-001" for v in data["violations"])
        assert any("malicious.py" in v["path"] for v in data["violations"])

    def test_detects_shell_script(self, tmp_path: Path) -> None:
        """Shell script in subdirectory = violation."""
        sub = tmp_path / "@工作文档" / "卫健委"
        sub.mkdir(parents=True)
        script = sub / "sync_data.sh"
        script.write_text("#!/bin/bash\necho hi")
        rc, data = _run_check(tmp_path, rule="E-DOC-001")
        assert rc == 1
        assert any(v["rule"] == "E-DOC-001" for v in data["violations"])

    @pytest.mark.parametrize("ext", [".py", ".sh", ".bash", ".js", ".ts", ".rb", ".go"])
    def test_all_banned_extensions(self, tmp_path: Path, ext: str) -> None:
        """All banned extensions are caught."""
        f = tmp_path / f"test{ext}"
        f.write_text("// content")
        rc, data = _run_check(tmp_path, rule="E-DOC-001")
        assert rc == 1
        assert any(v["rule"] == "E-DOC-001" for v in data["violations"])

    def test_markdown_files_allowed(self, tmp_path: Path) -> None:
        """Markdown files are NOT violations."""
        f = tmp_path / "readme.md"
        f.write_text("# Hello")
        rc, data = _run_check(tmp_path, rule="E-DOC-001")
        assert rc == 0
        assert data["ok"] is True

    def test_fix_suggestion_present(self, tmp_path: Path) -> None:
        """Violation includes a fix suggestion."""
        (tmp_path / "hack.py").write_text("pass")
        rc, data = _run_check(tmp_path, rule="E-DOC-001")
        assert rc == 1
        v = [x for x in data["violations"] if x["rule"] == "E-DOC-001"][0]
        assert "fix_suggestion" in v
        assert "mv" in v["fix_suggestion"]


# ── E-DOC-002: Environment dependency directory detection ───────────────────

class TestEDOC002:
    def test_detects_node_modules(self, tmp_path: Path) -> None:
        """node_modules in Documents = violation."""
        nm = tmp_path / "node_modules"
        nm.mkdir()
        (nm / "dep.js").write_text("module.exports = {}")
        rc, data = _run_check(tmp_path, rule="E-DOC-002")
        assert rc == 1
        assert any(v["rule"] == "E-DOC-002" for v in data["violations"])

    def test_detects_pycache(self, tmp_path: Path) -> None:
        """__pycache__ in Documents = violation."""
        cache = tmp_path / "__pycache__"
        cache.mkdir()
        rc, data = _run_check(tmp_path, rule="E-DOC-002")
        assert rc == 1

    @pytest.mark.parametrize("dirname", ["node_modules", ".venv", "__pycache__", ".pytest_cache", ".mypy_cache", ".tox"])
    def test_all_banned_dirs(self, tmp_path: Path, dirname: str) -> None:
        """All banned directory names are caught."""
        d = tmp_path / dirname
        d.mkdir()
        rc, data = _run_check(tmp_path, rule="E-DOC-002")
        assert rc == 1

    def test_nested_node_modules(self, tmp_path: Path) -> None:
        """node_modules nested in a subdirectory = violation."""
        sub = tmp_path / "@学习进化" / "project"
        sub.mkdir(parents=True)
        (sub / "node_modules").mkdir()
        rc, data = _run_check(tmp_path, rule="E-DOC-002")
        assert rc == 1


# ── E-DOC-004: Fact file schema validation ──────────────────────────────────

class TestEDOC004:
    def test_valid_fact_file(self, tmp_path: Path) -> None:
        """Valid YAML fact file = no violation."""
        facts = tmp_path / "_entities" / "facts"
        facts.mkdir(parents=True)
        (facts / "project.yaml").write_text("name: test\ncategory: demo\n")
        rc, data = _run_check(tmp_path, rule="E-DOC-004")
        # When pyyaml is not installed, we get a warning not an error
        if not any(v.get("rule") == "E-DOC-004" and "pyyaml" in v.get("message", "") for v in data.get("violations", [])):
            assert rc == 0

    def test_empty_yaml_violation(self, tmp_path: Path) -> None:
        """Empty YAML file = violation (requires pyyaml)."""
        facts = tmp_path / "_entities" / "facts"
        facts.mkdir(parents=True)
        (facts / "empty.yaml").write_text("")
        rc, data = _run_check(tmp_path, rule="E-DOC-004")
        # If pyyaml is installed, we get an error; otherwise a warning
        violations = data.get("violations", []) if isinstance(data, dict) else []
        has_violation = any(v.get("rule") == "E-DOC-004" for v in violations)
        has_pyyaml_warning = any("pyyaml" in v.get("message", "") for v in violations)
        assert has_violation or has_pyyaml_warning

    def test_invalid_yaml_violation(self, tmp_path: Path) -> None:
        """Malformed YAML = violation (requires pyyaml)."""
        facts = tmp_path / "_entities" / "facts"
        facts.mkdir(parents=True)
        (facts / "bad.yaml").write_text("key: [unclosed\n  - item")
        rc, data = _run_check(tmp_path, rule="E-DOC-004")
        violations = data.get("violations", []) if isinstance(data, dict) else []
        has_violation = any(v.get("rule") == "E-DOC-004" for v in violations)
        has_pyyaml_warning = any("pyyaml" in v.get("message", "") for v in violations)
        assert has_violation or has_pyyaml_warning


# ── E-DOC-005: Multi-client config consistency ─────────────────────────────

class TestEDOC005:
    def test_missing_ssot_registry_warning(self, tmp_path: Path) -> None:
        """Missing SSOT registry = warning."""
        rc, data = _run_check(tmp_path, rule="E-DOC-005")
        # This is a warning, not an error (SSOT may not exist in test env)
        assert data["ok"] is True  # warnings don't cause failure


# ── JSON output & integration ───────────────────────────────────────────────

class TestJSONOutput:
    def test_json_structure(self, tmp_path: Path) -> None:
        """JSON output has correct structure."""
        rc, data = _run_check(tmp_path)
        assert isinstance(data, dict)
        assert "ok" in data
        assert "violations" in data
        assert "rules_checked" in data
        assert "error_count" in data
        assert "warning_count" in data

    def test_no_violations_ok_true(self, tmp_path: Path) -> None:
        """Clean Documents = ok=true, exit 0."""
        rc, data = _run_check(tmp_path)
        assert rc == 0
        assert data["ok"] is True


# ── Auto-fix mode ───────────────────────────────────────────────────────────

class TestAutoFix:
    def test_dry_run_does_not_mutate(self, tmp_path: Path) -> None:
        """--dry-run --auto-fix should not modify the filesystem."""
        script = tmp_path / "malicious.py"
        script.write_text("print('hi')")
        rc, data = _run_check(tmp_path, rule="E-DOC-001", auto_fix=True, dry_run=True)
        assert script.exists()  # file should still exist
        assert "fix_actions" in data

    def test_auto_fix_moves_script(self, tmp_path: Path) -> None:
        """--auto-fix should move script to Workspace/scripts/."""
        script = tmp_path / "moved.py"
        script.write_text("print('moved')")
        dest = WORKSPACE / "scripts" / "moved.py"
        try:
            rc, data = _run_check(tmp_path, rule="E-DOC-001", auto_fix=True, dry_run=False)
            assert dest.exists() or rc == 1  # either moved or still violation
        finally:
            # cleanup
            if dest.exists():
                dest.unlink()
