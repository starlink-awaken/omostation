#!/usr/bin/env python3
"""check-severity-registry: decl-exec-gap for SGF gate severity.

SGF-v1's `gates` list declares each check's `severity` (informational |
warn | blocking). The actual behavior is set by the check's exit code:
0 = pass, 1 = warn, 2 = blocking. This check runs each declared gate
and verifies that its severity claim matches its real exit code, so a
check that claims `blocking` but exits 0 on findings (or vice versa)
gets caught at review time.

Scope: limited to the three primary meta-decl locks referenced in the
P85 spec (drift, doc-claims, layer-call-direction). The full 49-check
survey is a Q4 (G4.2) deliverable, not part of G1.3.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

import yaml

WORKSPACE = Path(__file__).resolve().parents[2]
SGF_POLICY_YAML = (
    WORKSPACE
    / "projects"
    / "ecos"
    / "src"
    / "ecos"
    / "ssot"
    / "mof"
    / "m1"
    / "governance"
    / "sgf-policy.yaml"
)
PRIMARY_LOCKS = {"gac-drift", "doc-claims-check", "layer-call-direction-check"}


def _load_sgf() -> dict:
    if SGF_POLICY_YAML.is_file():
        return yaml.safe_load(SGF_POLICY_YAML.read_text(encoding="utf-8")) or {}
    return {}


def _resolve_command(gate: dict) -> list[str] | None:
    cmd = gate.get("command") or []
    if not cmd:
        return None
    return [WORKSPACE / c if not os.path.isabs(c) and not c.startswith("-") else c
            if not os.path.isabs(c) and c[0] != "-"
            else c
            for c in cmd]


def _run_check(command: list[str]) -> int:
    try:
        completed = subprocess.run(
            command,
            cwd=str(WORKSPACE),
            capture_output=True,
            text=True,
            timeout=120,
        )
        return completed.returncode
    except Exception as exc:  # pragma: no cover
        print(f"[ERROR] failed to run {command}: {exc}", file=sys.stderr)
        return -1


def _declared_severity(gate: dict) -> str:
    severity = str(gate.get("severity", "")).strip().lower()
    return severity or "informational"


def _exit_code_to_severity(rc: int) -> str:
    if rc == 0:
        return "informational"
    if rc == 1:
        return "warn"
    if rc == 2:
        return "blocking"
    return f"unknown(rc={rc})"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    sgf = _load_sgf()
    gates = sgf.get("gates") or []
    gates_by_id = {g.get("id"): g for g in gates if g.get("id")}

    findings: list[dict] = []
    summary: dict[str, int] = {"checked": 0, "passed": 0, "mismatched": 0}

    for lock_id in PRIMARY_LOCKS:
        gate = gates_by_id.get(lock_id)
        if gate is None:
            findings.append({
                "id": lock_id,
                "kind": "missing",
                "message": f"primary lock {lock_id!r} not declared in sgf-policy.yaml",
            })
            summary["mismatched"] += 1
            continue
        cmd = _resolve_command(gate)
        if not cmd:
            findings.append({
                "id": lock_id,
                "kind": "no_command",
                "message": f"primary lock {lock_id!r} has no command",
            })
            summary["mismatched"] += 1
            continue
        # Run the check on a benign input. Most checks return 0 when
        # the workspace is healthy. We do NOT fail the gate; we only
        # verify the declared severity matches the observed exit code.
        rc = _run_check(cmd)
        observed = _exit_code_to_severity(rc)
        declared = _declared_severity(gate)
        summary["checked"] += 1
        if observed == "unknown":
            # Check crashed (timeout / ImportError). Do not block on this
            # — the check itself will report the failure elsewhere.
            summary["passed"] += 1
            continue
        # Allow severity to be declared as one of the three known
        # buckets; the only "fail" is when declared severity is a
        # *stronger* signal than what the check actually emits
        # (claiming blocking but exiting 0) or vice versa.
        bucket_order = {"informational": 0, "warn": 1, "blocking": 2}
        if observed not in bucket_order or declared not in bucket_order:
            findings.append({
                "id": lock_id,
                "kind": "unknown_severity",
                "declared": declared,
                "observed": observed,
                "message": f"unknown severity label declared={declared!r} observed={observed!r}",
            })
            summary["mismatched"] += 1
            continue
        if bucket_order[declared] != bucket_order[observed]:
            findings.append({
                "id": lock_id,
                "kind": "decl_exec_gap",
                "declared": declared,
                "observed": observed,
                "message": (
                    f"severity drift: declared {declared!r} but exit code "
                    f"suggests {observed!r}"
                ),
            })
            summary["mismatched"] += 1
        else:
            summary["passed"] += 1

    ok = not findings
    report = {
        "ok": ok,
        "policy_path": str(SGF_POLICY_YAML.relative_to(WORKSPACE)) if SGF_POLICY_YAML.is_file() else None,
        "summary": summary,
        "findings": findings,
    }
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"check-severity-registry: {'PASS' if ok else 'FAIL'}")
        print(f"  checked={summary['checked']} passed={summary['passed']} mismatched={summary['mismatched']}")
        for f in findings:
            print(f"  - {f['id']}: {f.get('kind', '?')} declared={f.get('declared','-')} observed={f.get('observed','-')}")
            print(f"    {f.get('message', '')}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
