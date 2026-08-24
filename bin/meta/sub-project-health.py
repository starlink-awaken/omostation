#!/usr/bin/env python3
"""
sub-project-health.py — Aggregate sub-project health status.

Usage:
  uv run python3 bin/meta/sub-project-health.py
  uv run python3 bin/meta/sub-project-health.py --json
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def run(cmd: str, cwd) -> tuple[int, str, str]:
    try:
        p = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True, timeout=120)
        return p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired:
        return 1, "", "timeout"


def get_subprojects() -> list:
    projects_dir = REPO_ROOT / "projects"
    if not projects_dir.exists():
        return []
    subprojects = []
    for d in sorted(projects_dir.iterdir()):
        if not d.is_dir():
            continue
        # Skip non-git directories
        if not (d / ".git").exists() and not (d / "pyproject.toml").exists():
            continue
        subprojects.append({
            "name": d.name,
            "path": str(d.relative_to(REPO_ROOT)),
            "has_git": (d / ".git").exists(),
        })
    return subprojects


def check_health(subproject: dict) -> dict:
    path = REPO_ROOT / subproject["path"]
    result = {
        "name": subproject["name"],
        "path": subproject["path"],
        "branch": "unknown",
        "tests": "unknown",
        "last_commit": "unknown",
        "health": "unknown",
    }

    # Check branch
    rc, out, err = run("git branch --show-current", cwd=path)
    if rc == 0 and out.strip():
        result["branch"] = out.strip()

    # Check if detached HEAD
    rc, out, err = run("git rev-parse --abbrev-ref HEAD", cwd=path)
    if rc == 0 and out.strip() == "HEAD":
        result["branch"] = "detached"

    # Check last commit
    rc, out, err = run("git log -1 --format=%cr --no-decorate", cwd=path)
    if rc == 0 and out.strip():
        result["last_commit"] = out.strip()

    # Determine health
    health = "green"
    if result["branch"] == "detached":
        # Detached HEAD is expected for worktree --init sub-projects
        # Health depends on last commit recency, not branch name
        if "day" in result["last_commit"].lower() or "week" in result["last_commit"].lower() or "month" in result["last_commit"].lower() or "minute" in result["last_commit"].lower() or "hour" in result["last_commit"].lower():
            try:
                num = int(''.join(filter(str.isdigit, result["last_commit"])))
                if "minute" in result["last_commit"].lower() or "hour" in result["last_commit"].lower():
                    health = "green"
                elif "day" in result["last_commit"].lower():
                    if num > 7:
                        health = "yellow"
                    else:
                        health = "green"
                elif "week" in result["last_commit"].lower():
                    if num > 4:
                        health = "red"
                    else:
                        health = "green"
                elif "month" in result["last_commit"].lower():
                    health = "yellow"
            except Exception:
                pass
        elif "year" in result["last_commit"].lower():
            health = "red"
        else:
            health = "yellow"
    elif "day" in result["last_commit"].lower() or "week" in result["last_commit"].lower() or "month" in result["last_commit"].lower():
        try:
            num = int(''.join(filter(str.isdigit, result["last_commit"])))
            if "day" in result["last_commit"].lower() and num > 7:
                health = "yellow"
            elif "week" in result["last_commit"].lower() and num > 4:
                health = "red"
            elif "month" in result["last_commit"].lower():
                health = "red"
        except Exception:
            pass
    elif "year" in result["last_commit"].lower():
        health = "red"

    result["health"] = health
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Sub-project health aggregator")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args()

    subprojects = get_subprojects()
    if not subprojects:
        print("No sub-projects found")
        sys.exit(0)

    results = []
    for sp in subprojects:
        results.append(check_health(sp))

    green = sum(1 for r in results if r["health"] == "green")
    yellow = sum(1 for r in results if r["health"] == "yellow")
    red = sum(1 for r in results if r["health"] == "red")

    if args.json:
        output = {
            "total": len(results),
            "green": green,
            "yellow": yellow,
            "red": red,
            "projects": results,
        }
        print(json.dumps(output, indent=2, ensure_ascii=False))
        sys.exit(0 if red == 0 else 1)

    print("Sub-project Health Report")
    print("=" * 70)
    print(f"{'Project':<20} {'Branch':<15} {'Last Commit':<20} {'Health'}")
    print("-" * 70)
    for r in results:
        health_icon = {"green": "🟢", "yellow": "🟡", "red": "🔴"}.get(r["health"], "⚪")
        print(f"{r['name']:<20} {r['branch']:<15} {r['last_commit']:<20} {health_icon} {r['health']}")
    print("=" * 70)
    print(f"Total: {len(results)} | 🟢 Green: {green} | 🟡 Yellow: {yellow} | 🔴 Red: {red}")
    if red > 0:
        print("WARNING: Some sub-projects are RED. Investigate immediately.")
        sys.exit(1)
    else:
        print("All sub-projects healthy.")


if __name__ == "__main__":
    main()
