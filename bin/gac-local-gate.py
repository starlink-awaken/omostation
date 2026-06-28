#!/usr/bin/env python3
"""Run the local Governance-as-Code gate used by hooks and CI."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


WORKSPACE = Path(__file__).resolve().parents[1]


CHECKS: tuple[tuple[str, list[str]], ...] = (
    ("gac-validate", ["bin/gac-validate.py", "--gate"]),
    ("gac-drift", ["bin/gac-drift.py"]),
    ("doc-ssot-lint", ["bin/doc-ssot-lint.py"]),
    ("doc-ssot-snapshots", ["scripts/check-doc-ssot-snapshots.py"]),
    ("doc-link-check", ["bin/doc-link-check.py"]),
)


def run_check(name: str, command: list[str]) -> dict[str, object]:
    cmd = [sys.executable, *command]
    result = subprocess.run(
        cmd,
        cwd=WORKSPACE,
        capture_output=True,
        text=True,
        check=False,
    )
    return {
        "name": name,
        "command": " ".join(command),
        "ok": result.returncode == 0,
        "returncode": result.returncode,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
    }


def run_gate() -> dict[str, object]:
    results = [run_check(name, command) for name, command in CHECKS]
    return {
        "ok": all(item["ok"] for item in results),
        "checks": results,
    }


def print_human(report: dict[str, object]) -> None:
    print("═══ GaC local gate ═══")
    for item in report["checks"]:
        status = "PASS" if item["ok"] else "FAIL"
        print(f"[{status}] {item['name']} :: {item['command']}")
        if not item["ok"]:
            if item["stdout"]:
                print(item["stdout"])
            if item["stderr"]:
                print(item["stderr"], file=sys.stderr)
    print("GaC local gate: " + ("PASS" if report["ok"] else "FAIL"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the shared local GaC gate")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    args = parser.parse_args()

    report = run_gate()
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_human(report)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
