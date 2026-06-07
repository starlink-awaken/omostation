#!/usr/bin/env python3
"""Auto-Heal Daemon MVP — Phase 3C System Immune Awakening.

Scans project test suites, diagnoses common failure patterns,
and attempts automated remediation.

Usage:
    python auto_heal_daemon.py --project runtime --auto-fix
    python auto_heal_daemon.py --all --report heal-report.json
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

WORKSPACE_ROOT = Path(__file__).resolve().parents[3]
PROJECTS_DIR = WORKSPACE_ROOT / "projects"

# ── Failure Patterns ───────────────────────────────────────────────

PATTERNS: list[dict[str, Any]] = [
    {
        "id": "missing-dep",
        "regex": r"ModuleNotFoundError: No module named ['\"](?P<module>[^'\"]+)['\"]",
        "description": "Python module not found (missing dependency)",
    },
    {
        "id": "uv-source-missing",
        "regex": r"Because (?P<package>[\w-]+) was not found in the package registry",
        "description": "uv cannot resolve a workspace/path dependency",
    },
    {
        "id": "hardcoded-localhost",
        "regex": r"(localhost|127\.0\.0\.1):(?P<port>\d+)",
        "description": "Hard-coded localhost endpoint detected in source",
    },
    {
        "id": "stderr-mismatch",
        "regex": r"AssertionError: assert ['\"](?P<text>[^'\"]+)['\"] in ['\"]['\"]",
        "description": "Test expects output in stdout but it's empty (likely in stderr)",
    },
    {
        "id": "import-cycle",
        "regex": r"ImportError: cannot import name ['\"](?P<name>[^'\"]+)['\"]",
        "description": "Import cycle or missing re-export",
    },
]


# ── Data Structures ────────────────────────────────────────────────

@dataclass
class Failure:
    test_name: str
    error_type: str
    raw_output: str
    matched_patterns: list[str] = field(default_factory=list)
    suggested_fix: str = ""
    fix_applied: bool = False


@dataclass
class ProjectScan:
    project: str
    total_tests: int = 0
    passed: int = 0
    failed: int = 0
    errors: int = 0
    failures: list[Failure] = field(default_factory=list)


# ── Core Functions ─────────────────────────────────────────────────


def _run_tests(project: str, timeout: int = 300) -> tuple[int, str, str]:
    """Run pytest for a project and return (rc, stdout, stderr)."""
    proj_path = PROJECTS_DIR / project
    if not proj_path.exists():
        raise FileNotFoundError(f"Project not found: {project}")

    cmd = ["uv", "run", "pytest", "tests/", "-q", "--tb=short"]
    # Agora e2e tests need external services; skip them in auto-heal scans
    if project == "agora":
        cmd = ["uv", "run", "pytest", "tests/", "--ignore=tests/e2e", "-q", "--tb=short"]

    result = subprocess.run(
        cmd,
        cwd=str(proj_path),
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return result.returncode, result.stdout, result.stderr


def _parse_pytest_summary(stdout: str, stderr: str) -> dict[str, int]:
    """Extract test counts from pytest short summary."""
    combined = stdout + "\n" + stderr
    m = re.search(r"(\d+) passed", combined)
    passed = int(m.group(1)) if m else 0
    m = re.search(r"(\d+) failed", combined)
    failed = int(m.group(1)) if m else 0
    m = re.search(r"(\d+) error", combined)
    errors = int(m.group(1)) if m else 0
    m = re.search(r"(\d+) skipped", combined)
    skipped = int(m.group(1)) if m else 0
    total = passed + failed + errors + skipped
    return {"total": total, "passed": passed, "failed": failed, "errors": errors, "skipped": skipped}


def _extract_failures(stdout: str, stderr: str) -> list[Failure]:
    """Parse pytest output into individual Failure objects."""
    combined = stdout + "\n" + stderr
    failures: list[Failure] = []

    # Pytest short format: "FAILED tests/file.py::TestClass::test_method"
    for line in combined.splitlines():
        m = re.match(r"FAILED\s+(\S+)", line)
        if m:
            test_name = m.group(1)
            # Extract traceback section for this test
            # Heuristic: find the block between "FAILED <name>" and next "FAILED" or "=" line
            failures.append(Failure(test_name=test_name, error_type="AssertionError", raw_output=""))

    # If we can't parse individual failures, create a single catch-all
    if not failures and ("FAILED" in combined or "ERROR" in combined):
        failures.append(Failure(test_name="<unknown>", error_type="Unknown", raw_output=combined[-2000:]))

    return failures


def _diagnose(failure: Failure) -> None:
    """Match failure output against known patterns and set suggested_fix."""
    text = failure.raw_output
    for pat in PATTERNS:
        match = re.search(pat["regex"], text)
        if match:
            failure.matched_patterns.append(pat["id"])
            if pat["id"] == "missing-dep":
                mod = match.group("module")
                failure.suggested_fix = f"Add '{mod}' to pyproject.toml dependencies"
            elif pat["id"] == "uv-source-missing":
                pkg = match.group("package")
                failure.suggested_fix = f"Add [tool.uv.sources] entry for '{pkg}'"
            elif pat["id"] == "hardcoded-localhost":
                failure.suggested_fix = "Replace hard-coded endpoint with os.environ.get(...) fallback"
            elif pat["id"] == "stderr-mismatch":
                failure.suggested_fix = "Change captured.out to captured.err in test assertion"
            elif pat["id"] == "import-cycle":
                failure.suggested_fix = "Create backward-compat shim __init__.py or fix import order"


def _try_fix(project: str, failure: Failure) -> bool:
    """Attempt an automated fix. Returns True if a change was made."""
    if not failure.matched_patterns:
        return False

    proj_path = PROJECTS_DIR / project
    pattern = failure.matched_patterns[0]

    # Fix: uv-source-missing — currently manual; requires pyproject.toml edit
    if pattern == "uv-source-missing":
        # We can't safely auto-edit pyproject.toml without more context
        return False

    # Fix: missing-dep — try to uv add
    if pattern == "missing-dep":
        m = re.search(r"No module named ['\"]([^'\"]+)['\"]", failure.raw_output)
        if m:
            mod = m.group(1)
            # Map common module -> package names
            pkg_map = {
                "fastapi": "fastapi",
                "requests": "requests",
                "httpx": "httpx",
            }
            pkg = pkg_map.get(mod)
            if pkg:
                result = subprocess.run(
                    ["uv", "add", "--package", project, pkg],
                    cwd=str(PROJECTS_DIR / "kairon" if project == "kos" else proj_path),
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                return result.returncode == 0
        return False

    # Fix: stderr-mismatch — auto-edit test file
    if pattern == "stderr-mismatch":
        # Find the test file and change captured.out -> captured.err
        test_file = proj_path / failure.test_name.split("::")[0]
        if test_file.exists():
            source = test_file.read_text(encoding="utf-8")
            # Replace assert ... in captured.out for error-checking lines
            new_source = re.sub(
                r'(assert\s+["\'].*?["\']\s+in\s+)captured\.out',
                r'\1captured.err',
                source,
            )
            if new_source != source:
                test_file.write_text(new_source, encoding="utf-8")
                return True
        return False

    return False


def scan_project(project: str, auto_fix: bool = False) -> ProjectScan:
    """Run tests, diagnose failures, optionally apply fixes."""
    scan = ProjectScan(project=project)
    try:
        rc, stdout, stderr = _run_tests(project)
    except subprocess.TimeoutExpired:
        scan.failures.append(Failure(test_name="<suite>", error_type="Timeout", raw_output="pytest timed out"))
        return scan
    except FileNotFoundError as e:
        scan.failures.append(Failure(test_name="<suite>", error_type="NotFound", raw_output=str(e)))
        return scan

    summary = _parse_pytest_summary(stdout, stderr)
    scan.total_tests = summary["total"]
    scan.passed = summary["passed"]
    scan.failed = summary["failed"]
    scan.errors = summary["errors"]

    if rc != 0:
        failures = _extract_failures(stdout, stderr)
        for f in failures:
            f.raw_output = stdout + "\n" + stderr
            _diagnose(f)
            if auto_fix:
                f.fix_applied = _try_fix(project, f)
        scan.failures = failures

    return scan


# ── CLI ────────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Auto-Heal Daemon MVP")
    parser.add_argument("--project", action="append", help="Project to scan (repeatable)")
    parser.add_argument("--all", action="store_true", help="Scan all active Python projects")
    parser.add_argument("--auto-fix", action="store_true", help="Attempt automated fixes")
    parser.add_argument("--report", help="Write JSON report to file")
    args = parser.parse_args(argv)

    projects = args.project or []
    if args.all:
        projects = ["agora", "cockpit", "ecos", "kairon", "metaos", "omo", "runtime"]

    if not projects:
        parser.error("Specify --project or --all")

    results: list[ProjectScan] = []
    for proj in projects:
        print(f"\n🔍 Scanning {proj} ...")
        scan = scan_project(proj, auto_fix=args.auto_fix)
        results.append(scan)
        status = "✅ PASS" if scan.failed == 0 and scan.errors == 0 else "⚠️  FAIL"
        print(f"   {status}  {scan.passed}/{scan.total_tests} passed  ({scan.failed} failed, {scan.errors} errors)")
        for f in scan.failures:
            print(f"   • {f.test_name}: {', '.join(f.matched_patterns) or 'unmatched'}")
            if f.suggested_fix:
                print(f"     💡 {f.suggested_fix}")
            if f.fix_applied:
                print(f"     🔧 Fix applied")

    if args.report:
        report_data = [asdict(r) for r in results]
        Path(args.report).write_text(json.dumps(report_data, indent=2, default=str), encoding="utf-8")
        print(f"\n📄 Report written to {args.report}")

    total_failed = sum(r.failed + r.errors for r in results)
    return 0 if total_failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
