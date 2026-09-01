#!/usr/bin/env python3
"""本地运行拓扑级联测试 (cascading-test.yml 的本地等价物)。

Usage:
    python bin/gac/cascading-test-local.py [base_ref]

Example:
    python bin/gac/cascading-test-local.py origin/main
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

WS = Path(__file__).resolve().parents[2]


def get_changed_projects(base: str = "origin/main") -> list[str]:
    """Get list of projects with changes since base."""
    result = subprocess.run(
        ["git", "diff", "--name-only", f"{base}...", "HEAD"],
        capture_output=True,
        text=True,
        cwd=WS,
    )
    projects: set[str] = set()
    for line in result.stdout.strip().splitlines():
        if line.startswith("projects/"):
            parts = line.split("/")
            if len(parts) >= 2 and (WS / "projects" / parts[1]).is_dir():
                projects.add(parts[1])
    return sorted(projects)


def get_affected_projects(changed: list[str]) -> list[str]:
    """Run affected-graph.py to get full affected project list."""
    if not changed:
        return []
    result = subprocess.run(
        [sys.executable, "bin/gac/affected-graph.py", "--changed-projects", *changed, "--json"],
        capture_output=True,
        text=True,
        cwd=WS,
    )
    if result.returncode != 0:
        print(f"affected-graph.py failed: {result.stderr}", file=sys.stderr)
        return changed
    try:
        data = json.loads(result.stdout)
        return data.get("affected_projects", changed)
    except json.JSONDecodeError:
        return changed


def run_tests(projects: list[str]) -> int:
    """Run tests for each project."""
    for proj in projects:
        proj_dir = WS / "projects" / proj
        if not (proj_dir / "tests").is_dir() or not (proj_dir / "pyproject.toml").is_file():
            print(f"⏭️  Skip {proj}: no tests/ or pyproject.toml")
            continue

        print(f"\n🧪 Testing: {proj}")

        # Sync deps
        r = subprocess.run(["uv", "sync", "--quiet"], cwd=proj_dir)
        if r.returncode != 0:
            print(f"  ❌ uv sync failed")
            return r.returncode

        # Run tests (skip e2e and integration for speed)
        r = subprocess.run(
            [
                "uv",
                "run",
                "pytest",
                "-q",
                "--ignore=tests/e2e",
                "--ignore=tests/integration",
            ],
            cwd=proj_dir,
        )
        if r.returncode != 0:
            print(f"  ❌ Tests failed")
            return r.returncode
        print(f"  ✓ Passed")

    return 0


def main():
    parser = argparse.ArgumentParser(description="Run cascading tests locally")
    parser.add_argument(
        "base",
        nargs="?",
        default="origin/main",
        help="Base ref to compare against (default: origin/main)",
    )
    args = parser.parse_args()

    # Step 1: Get changed projects
    changed = get_changed_projects(args.base)
    if not changed:
        print("No project changes detected")
        return 0
    print(f"Changed projects: {changed}")

    # Step 2: Get affected projects
    affected = get_affected_projects(changed)
    if affected != changed:
        print(f"Affected projects (with deps): {affected}")

    # Step 3: Run tests
    return run_tests(affected)


if __name__ == "__main__":
    sys.exit(main())
