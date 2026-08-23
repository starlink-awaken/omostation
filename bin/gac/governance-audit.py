#!/usr/bin/env python3
"""Governance audit — comprehensive health check for the workspace."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
REPORT_PATH = WORKSPACE / ".omo/_truth/registry/governance-audit.json"


def run_command(cmd: list[str], cwd: Path = WORKSPACE) -> tuple[int, str]:
    """Run command and return (exit_code, output)."""
    try:
        proc = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
        )
        return proc.returncode, proc.stdout + proc.stderr
    except Exception as exc:
        return 2, str(exc)


def main() -> int:
    checks = {
        "ci_local_fast": run_command(["make", "ci-local-fast"]),
        "gac_validate": run_command(["bin/gac/gac-validate.py", "--gate"]),
        "ruff_drift": run_command(["python3", "bin/gac/ruff-config-drift.py"]),
        "mof_schema": run_command(["python3", "projects/ecos/src/ecos/ssot/tools/mof-schema-validate.py", "--json"]),
        "service_config": run_command(["bin/mof/gen-service-configs.py", "--check", "--json"]),
    }

    results = {}
    all_passed = True
    for name, (exit_code, output) in checks.items():
        passed = exit_code == 0
        if not passed:
            all_passed = False
        results[name] = {
            "exit_code": exit_code,
            "passed": passed,
            "output": output,
        }

    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "overall_passed": all_passed,
        "checks": results,
    }

    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
