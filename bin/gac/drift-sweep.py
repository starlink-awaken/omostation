#!/usr/bin/env python3
"""drift-sweep — aggregate all drift checks into a single weekly report.

Why: rounds 5-8 added several independent drift detectors (state freshness,
capability drift, bin convergence, ADR validity, runbook refs, anti-corrosion).
Each is individually wired into the gate, but operators need a single "what
is drifting right now" view for weekly maintenance.

This tool runs each check in sequence (never blocks on failure), aggregates
the results into a unified report, and emits an observability event if any
check has findings.

Usage:
  python3 bin/gac/drift-sweep.py                # human output
  python3 bin/gac/drift-sweep.py --json         # machine-readable
  python3 bin/gac/drift-sweep.py --emit-event   # also emit observability event

Exit codes:
  0 = no drift detected
  1 = drift found (informational, not gate-blocking)
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]

# Each entry: (name, command list, json_parser)
# json_parser extracts a count of issues from the check's stdout JSON.
CHECKS: list[tuple[str, list[str]]] = [
    ("state-freshness", ["bin/gac/state-freshness-check.py", "--json"]),
    ("capability-drift", ["bin/mof/check-mof-capabilities-drift.py"]),
    ("bin-convergence", ["bin/ssot/bin-scripts-convergence-audit.py", "--check", "--json"]),
    ("adr-drift", ["bin/adr/adr-drift-check.py", "--json"]),
    ("runbook-refs", ["bin/ssot/validate-runbook-refs.py", "--json"]),
    ("anti-corrosion", ["bin/gac/anti-corrosion-check.py", "--json"]),
]


def _run_check(name: str, cmd: list[str]) -> dict:
    """Run a check and extract issue count from its output."""
    result = {
        "name": name,
        "command": " ".join(cmd),
        "ok": False,
        "issues": None,
        "detail": "",
        "error": None,
    }
    try:
        proc = subprocess.run(
            [sys.executable] + cmd,
            cwd=WORKSPACE,
            capture_output=True,
            text=True,
            timeout=60,
        )
        result["returncode"] = proc.returncode

        # Parse stdout as JSON where possible (strip non-JSON prefix lines)
        stdout = proc.stdout
        data = None
        # Find first '{' and try parsing from there
        json_start = stdout.find("{")
        if json_start >= 0:
            try:
                data = json.loads(stdout[json_start:])
            except json.JSONDecodeError:
                data = None

        # Extract issue counts per tool
        if name == "state-freshness":
            stale = sum(1 for r in data.get("results", []) if not r.get("ok"))
            expired = data.get("files_expired", 0)
            result["issues"] = stale + expired
            result["ok"] = proc.returncode == 0
        elif name == "adr-drift":
            result["issues"] = data.get("total_issues", 0)
            result["ok"] = result["issues"] == 0
        elif name == "runbook-refs":
            result["issues"] = data.get("broken_count", 0)
            result["ok"] = result["issues"] == 0
        elif name == "anti-corrosion":
            checks = data.get("checks", {})
            fails = sum(1 for v in checks.values() if not v.get("ok"))
            result["issues"] = fails
            result["ok"] = fails == 0
        else:
            # Generic: non-zero exit = issues
            result["issues"] = 1 if proc.returncode != 0 else 0
            result["ok"] = proc.returncode == 0

        # Truncate detail for report
        detail_lines = [
            ln for ln in (proc.stdout + proc.stderr).splitlines()
            if ln.strip() and not ln.strip().startswith("{")
        ]
        result["detail"] = "\n".join(detail_lines[:10])

    except subprocess.TimeoutExpired:
        result["error"] = "timeout after 60s"
    except FileNotFoundError:
        result["error"] = f"script not found: {cmd[0]}"
    except Exception as exc:
        result["error"] = str(exc)[:200]

    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--emit-event", action="store_true",
                       help="Also emit observability event if drift found")
    args = parser.parse_args(argv)

    now = datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")

    results = []
    total_issues = 0
    failing_checks = []

    for name, cmd in CHECKS:
        r = _run_check(name, cmd)
        results.append(r)
        if r.get("issues") is not None:
            total_issues += r["issues"]
        if not r.get("ok"):
            failing_checks.append(name)

    summary = {
        "ts": now,
        "checks_run": len(results),
        "total_issues": total_issues,
        "failing_checks": failing_checks,
        "healthy": len(failing_checks) == 0,
        "results": results,
    }

    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        status = "✅ HEALTHY" if summary["healthy"] else f"⚠️  DRIFT ({total_issues} issues)"
        print(f"═══ Drift Sweep ═══ {status}")
        print(f"   ts: {now}")
        print(f"   checks: {len(results)}  issues: {total_issues}")
        print()
        for r in results:
            icon = "✅" if r.get("ok") else "❌"
            issues = r.get("issues", "?")
            err = f" ERROR: {r['error']}" if r.get("error") else ""
            print(f"  {icon} {r['name']:<20} issues={issues}{err}")
        print()
        if failing_checks:
            print(f"failing: {', '.join(failing_checks)}")
            print("run individual checks with --json for details")

    return 1 if not summary["healthy"] else 0


if __name__ == "__main__":
    raise SystemExit(main())