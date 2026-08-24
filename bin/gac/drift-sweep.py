#!/usr/bin/env python3
"""
drift-sweep.py — Weekly anti-corruption sweep.

Usage:
  uv run python3 bin/gac/drift-sweep.py
  uv run python3 bin/gac/drift-sweep.py --json
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
        p = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True, timeout=300)
        return p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired:
        return 1, "", "timeout"


def check_ssot_pointer_drift() -> dict:
    rc, out, err = run("python3 bin/ssot/doc-ssot-lint.py 2>&1 | tail -20")
    return {
        "check": "ssot_pointer_drift",
        "pass": rc == 0,
        "output": out.strip()[-500:] if out else err.strip()[-500:],
    }


def check_mof_capability_drift() -> dict:
    rc, out, err = run("python3 bin/gac/mof-capabilities-drift-check.py 2>&1 | tail -20")
    return {
        "check": "mof_capability_drift",
        "pass": rc == 0,
        "output": out.strip()[-500:] if out else err.strip()[-500:],
    }


def check_submodule_pointer_drift() -> dict:
    rc, out, err = run("bash bin/ssot/submodule-pointer-transaction.sh --dry-run 2>&1 | tail -20")
    return {
        "check": "submodule_pointer_drift",
        "pass": rc == 0,
        "output": out.strip()[-500:] if out else err.strip()[-500:],
    }


def check_adr_link_validity() -> dict:
    adr_dir = REPO_ROOT / ".omo" / "_knowledge" / "decisions"
    if not adr_dir.exists():
        return {"check": "adr_link_validity", "pass": True, "output": "No ADR directory"}
    broken = 0
    total = 0
    for f in adr_dir.glob("*.md"):
        text = f.read_text(errors="ignore")
        for m in __import__("re").finditer(r"\[.*?\]\((.*?)\)", text):
            target = m.group(1)
            if target.startswith("/"):
                target_path = Path(target)
                if not target_path.exists() and not target.startswith("http"):
                    broken += 1
                total += 1
    return {
        "check": "adr_link_validity",
        "pass": broken == 0,
        "output": f"Checked {total} links, {broken} broken" if total > 0 else "No links found",
    }


def check_runbook_command_validity() -> dict:
    import glob
    runbooks = glob.glob("docs/operations/runbook-*.md")
    broken = []
    for rb in runbooks:
        text = Path(rb).read_text(errors="ignore")
        for m in __import__("re").finditer(r"`(bin/[^`]+)`", text):
            cmd_path = m.group(1).split()[0]
            if not (REPO_ROOT / cmd_path).exists():
                broken.append(f"{rb}: {cmd_path}")
    return {
        "check": "runbook_command_validity",
        "pass": len(broken) == 0,
        "output": f"Checked {len(runbooks)} runbooks, {len(broken)} broken commands" + (f": {broken[0]}" if broken else ""),
    }


def check_doc_link_validity() -> dict:
    rc, out, err = run("python3 bin/gac/doc-link-check.py 2>&1 | tail -20")
    return {
        "check": "doc_link_validity",
        "pass": rc == 0,
        "output": out.strip()[-500:] if out else err.strip()[-500:],
    }


def check_doc_hardcoded_values() -> dict:
    rc, out, err = run("python3 bin/gac/hardcode-scan.py 2>&1 | tail -20")
    return {
        "check": "doc_hardcoded_values",
        "pass": rc == 0,
        "output": out.strip()[-500:] if out else err.strip()[-500:],
    }


def check_script_registry_coverage() -> dict:
    rc, out, err = run("uv run python3 bin/ssot/script-registry.py validate 2>&1 | tail -10")
    return {
        "check": "script_registry_coverage",
        "pass": rc == 0,
        "output": out.strip()[-500:] if out else err.strip()[-500:],
    }


def check_layer_contract_compliance() -> dict:
    rc, out, err = run("make check-layers 2>&1 | tail -20")
    return {
        "check": "layer_contract_compliance",
        "pass": rc == 0,
        "output": out.strip()[-500:] if out else err.strip()[-500:],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Weekly drift sweep")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args()

    checks = [
        check_ssot_pointer_drift(),
        check_submodule_pointer_drift(),
        check_adr_link_validity(),
        check_runbook_command_validity(),
        check_doc_link_validity(),
        check_script_registry_coverage(),
        check_layer_contract_compliance(),
    ]

    passed = sum(1 for c in checks if c["pass"])
    failed = sum(1 for c in checks if not c["pass"])

    if args.json:
        result = {
            "timestamp": "2026-08-24T09:00:00Z",
            "sweep_id": "sweep-2026-08-24",
            "results": checks,
            "summary": {"pass": passed, "fail": failed, "total": len(checks)},
        }
        print(json.dumps(result, indent=2, ensure_ascii=False))
        sys.exit(0 if failed == 0 else 1)

    print("Weekly Drift Sweep")
    print("=" * 50)
    for c in checks:
        status = "PASS" if c["pass"] else "FAIL"
        print(f"[{status}] {c['check']}")
        if c["output"]:
            for line in c["output"].splitlines()[:3]:
                print(f"       {line}")
    print("=" * 50)
    print(f"Result: {passed} passed, {failed} failed, {len(checks)} total")
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
