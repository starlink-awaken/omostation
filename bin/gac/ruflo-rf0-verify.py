#!/usr/bin/env python3
"""Ruflo RF0 read-only admission verifier.

The verifier never initializes Ruflo in the canonical workspace and never
starts or stops a daemon.  Ruflo is probed only inside an isolated temporary
directory; commands that Ruflo may use for local state creation therefore
cannot write into the repository.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any

RUFLO = "/opt/homebrew/bin/ruflo"
TIMEOUT_S = 20
FORBIDDEN_RUFLO_TOKENS = frozenset({
    "init",
    "start",
    "stop",
    "restart",
    "connect",
    "sync",
    "push",
    "pull",
    "claims",
    "run",
})


def _run(argv: list[str], cwd: Path) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            argv,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=TIMEOUT_S,
            check=False,
        )
        return {
            "argv": argv,
            "rc": completed.returncode,
            "stdout": completed.stdout or "",
            "stderr": completed.stderr or "",
        }
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {
            "argv": argv,
            "rc": 124,
            "stdout": "",
            "stderr": f"unavailable or timeout after {TIMEOUT_S}s: {type(exc).__name__}",
        }


def _doctor_summary(stdout: str) -> dict[str, int | None]:
    match = re.search(r"Summary:\s*(\d+)\s+passed,\s*(\d+)\s+warnings", stdout)
    if not match:
        return {"passed": None, "warnings": None}
    return {"passed": int(match.group(1)), "warnings": int(match.group(2))}


def _daemon_state(stdout: str) -> tuple[bool, bool]:
    status_match = re.search(r"Status:.*?(STOPPED|RUNNING)", stdout, re.IGNORECASE)
    workers_match = re.search(r"AI Workers:\s*(off|on)", stdout, re.IGNORECASE)
    return (
        bool(status_match and status_match.group(1).upper() == "STOPPED"),
        bool(workers_match and workers_match.group(1).lower() == "off"),
    )


def _dependency_guard(results: list[dict[str, Any]]) -> tuple[bool, list[str]]:
    offenders: list[str] = []
    for result in results:
        argv = result.get("argv") if isinstance(result.get("argv"), list) else []
        if not argv or argv[0] != RUFLO:
            offenders.append("non-ruflo-command")
            continue
        for token in argv[1:]:
            if token in FORBIDDEN_RUFLO_TOKENS:
                offenders.append(str(token))
    return not offenders, sorted(set(offenders))


def build_report() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="ruflo-rf0-verify-") as temp_dir:
        cwd = Path(temp_dir)
        results = [
            _run([RUFLO, "version"], cwd),
            _run([RUFLO, "doctor"], cwd),
            _run([RUFLO, "daemon", "status"], cwd),
            _run([RUFLO, "status"], cwd),
        ]

    version_result, doctor_result, daemon_result, status_result = results
    version_match = re.search(r"(?m)^\s*(\d+\.\d+\.\d+)\s*$", version_result["stdout"])
    doctor_ok = (
        doctor_result["rc"] == 0
        and "All checks passed" in doctor_result["stdout"]
        and _doctor_summary(doctor_result["stdout"])["passed"] is not None
    )
    daemon_stopped, workers_off = _daemon_state(daemon_result["stdout"])
    status_output = f"{status_result['stdout']}\n{status_result['stderr']}"
    isolated_not_initialized = (
        status_result["rc"] != 0
        and "not initialized" in status_output.lower()
    )
    dependency_ok, offenders = _dependency_guard(results)

    checks = {
        "binary": bool(version_result["rc"] == 0 and version_match),
        "doctor": doctor_ok,
        "daemon_stopped": daemon_result["rc"] == 0 and daemon_stopped,
        "workers_off": daemon_result["rc"] == 0 and workers_off,
        "no_second_queue": bool(daemon_stopped and workers_off and isolated_not_initialized),
        "cross_agent_dependency_zero": dependency_ok,
    }
    doctor_summary = _doctor_summary(doctor_result["stdout"])
    return {
        "schema": "ruflo-rf0-verify/v1",
        "ok": all(checks.values()),
        "checks": checks,
        "version": version_match.group(1) if version_match else None,
        "doctor_summary": doctor_summary,
        "daemon": {
            "status": "STOPPED" if daemon_stopped else "UNKNOWN",
            "workers_off": workers_off,
        },
        "guard": {
            "offenders": offenders,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Emit JSON report")
    args = parser.parse_args(argv)
    report = build_report()
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        failed = [name for name, ok in report["checks"].items() if not ok]
        print(
            f"ruflo-rf0-verify: ok={report['ok']} version={report['version']} "
            f"failed={','.join(failed) if failed else 'none'}"
        )
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
