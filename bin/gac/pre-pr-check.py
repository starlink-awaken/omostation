#!/usr/bin/env python3
"""
pre-pr-check.py — Pre-PR sanity checklist for agents and humans.

Usage:
  uv run python3 bin/gac/pre-pr-check.py
  uv run python3 bin/gac/pre-pr-check.py --json
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def run(cmd: str, cwd: Path = REPO_ROOT) -> tuple[int, str, str]:
    try:
        p = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True, timeout=120)
        return p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired:
        return 1, "", "timeout"


def check_tests() -> dict:
    rc, out, err = run("make test-diff 2>/dev/null || uv run pytest tests/ -q --tb=no 2>/dev/null || echo 'NO_TESTS'")
    return {
        "check": "tests",
        "pass": rc == 0 and "passed" in out.lower(),
        "output": out.strip()[:500] if out else err.strip()[:500],
    }


def check_gate() -> dict:
    rc, out, err = run("make gac-local-gate 2>&1 | tail -20")
    return {
        "check": "gate",
        "pass": rc == 0 and "PASS" in out,
        "output": out.strip()[:500] if out else err.strip()[:500],
    }


def check_script_registry() -> dict:
    rc, out, err = run("uv run python3 bin/ssot/script-registry.py validate")
    return {
        "check": "script-registry",
        "pass": rc == 0,
        "output": out.strip()[:500] if out else err.strip()[:500],
    }


def check_secrets() -> dict:
    rc, out, err = run("git diff --cached --name-only 2>/dev/null | head -20")
    files = [f.strip() for f in out.splitlines() if f.strip()]
    secret_patterns = ["password", "secret", "token", "api_key", "apikey", "private_key", "credential"]
    violations = []
    for f in files:
        if any(p in f.lower() for p in secret_patterns):
            violations.append(f)
    return {
        "check": "secrets",
        "pass": len(violations) == 0,
        "output": f"Checked {len(files)} files; {len(violations)} potential secret files" if files else "No staged files",
    }


def check_docs_updated() -> dict:
    rc, out, err = run("git diff --name-only 2>/dev/null")
    files = [f.strip() for f in out.splitlines() if f.strip()]
    doc_files = [f for f in files if f.endswith(".md") or f.endswith(".yaml") or f.endswith(".json")]
    code_files = [f for f in files if f.endswith(".py") or f.endswith(".ts") or f.endswith(".sh")]
    if code_files and not doc_files:
        return {
            "check": "docs-updated",
            "pass": False,
            "output": f"Code changes ({len(code_files)} files) without documentation updates",
        }
    return {
        "check": "docs-updated",
        "pass": True,
        "output": f"OK: {len(doc_files)} doc files, {len(code_files)} code files",
    }


def check_commit_message() -> dict:
    rc, out, err = run("git log -1 --format=%B 2>/dev/null")
    msg = out.strip()
    if not msg:
        return {"check": "commit-message", "pass": True, "output": "No commits yet"}
    conventional = any(msg.startswith(p) for p in ["feat:", "fix:", "docs:", "refactor:", "test:", "chore:", "ci:", "build:", "ops:", "perf:", "style:", "revert:"])
    return {
        "check": "commit-message",
        "pass": conventional,
        "output": f"Message: {msg[:100]}..." if len(msg) > 100 else f"Message: {msg}",
    }


def check_runbook_references() -> dict:
    rc, out, err = run("python3 -c \"import yaml,glob; docs=glob.glob('docs/operations/runbook-*.md', recursive=True); print(len(docs))\"" )
    count = int(out.strip()) if out.strip().isdigit() else 0
    return {
        "check": "runbook-references",
        "pass": True,
        "output": f"{count} runbooks found (detailed check requires drift-sweep.py)",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Pre-PR sanity checklist")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args()

    checks = [
        check_tests(),
        check_gate(),
        check_script_registry(),
        check_secrets(),
        check_docs_updated(),
        check_commit_message(),
        check_runbook_references(),
    ]

    failures = [c for c in checks if not c["pass"]]

    if args.json:
        print(json.dumps({"checks": checks, "failures": len(failures), "pass": len(failures) == 0}, indent=2))
        sys.exit(0 if len(failures) == 0 else 1)

    print("Pre-PR Checklist")
    print("=" * 50)
    for c in checks:
        status = "PASS" if c["pass"] else "FAIL"
        print(f"[{status}] {c['check']}")
        if c["output"]:
            for line in c["output"].splitlines()[:5]:
                print(f"       {line}")

    print("=" * 50)
    if failures:
        print(f"FAILED: {len(failures)} check(s) failed")
        for c in failures:
            print(f"  - {c['check']}")
        sys.exit(1)
    else:
        print("ALL CHECKS PASSED")
        sys.exit(0)


if __name__ == "__main__":
    main()
