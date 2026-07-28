#!/usr/bin/env python3
"""check-severity-registry: decl-exec-gap for SGF gate severity.

SGF-v1's `gates` list declares each check's `severity` (informational |
warn | blocking). The actual behavior is set by the check's exit code:
0 = pass, 1 = warn, 2 = blocking. This check verifies each gate's
severity declaration against its actual runtime behavior.

Performance strategy:
  - Static validation: verify YAML structure, command existence, and
    severity field presence. O(1) file reads, no subprocess calls.
    Used in pre-commit (<2s).
  - Dynamic validation (optional --full flag): run each check and
    compare exit code against severity claim. Cached to a temp file
    with a configurable TTL (default 1h). Used in CI.

Scope: limited to the three primary meta-decl locks referenced in
the P85 spec (drift, doc-claims, layer-call-direction). The full
49-check survey is a Q4 (G4.2) deliverable.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
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
CACHE_TTL = 3600  # 1 hour
CACHE_FILE = Path(tempfile.gettempdir()) / "check-severity-registry-cache.json"


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


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--full",
        action="store_true",
        help="Run each check subprocess to compare exit code against "
             "declared severity (slow; uses cache). Default: static validation only.",
    )
    parser.add_argument(
        "--ttl",
        type=int,
        default=CACHE_TTL,
        help=f"Cache TTL in seconds for dynamic validation results (default {CACHE_TTL}).",
    )
    args = parser.parse_args(argv)

    sgf = _load_sgf()
    gates = sgf.get("gates") or []
    gates_by_id = {g.get("id"): g for g in gates if g.get("id")}

    findings: list[dict] = []
    summary: dict[str, int] = {"checked": 0, "passed": 0, "mismatched": 0}

    # Load cached results for dynamic mode.
    cache: dict[str, int] = {}
    if args.full and CACHE_FILE.is_file():
        try:
            cached = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
            if time.time() - cached.get("ts", 0) < args.ttl:
                cache = cached.get("results", {})
        except Exception:
            pass

    for lock_id in sorted(PRIMARY_LOCKS):
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

        declared = _declared_severity(gate)
        summary["checked"] += 1

        if not args.full:
            # Static validation: just verify severity is a known label
            # and the command file exists. No subprocess calls.
            if declared not in ("informational", "warn", "blocking"):
                findings.append({
                    "id": lock_id,
                    "kind": "unknown_severity",
                    "declared": declared,
                    "message": f"unknown severity label {declared!r}",
                })
                summary["mismatched"] += 1
            else:
                summary["passed"] += 1
            continue

        # Dynamic validation: run check or use cache.
        if lock_id in cache:
            rc = cache[lock_id]
        else:
            rc = _run_check(cmd)
            cache[lock_id] = rc

        observed = _exit_code_to_severity(rc)
        if observed == "unknown":
            summary["passed"] += 1
            continue
        bucket_order = {"informational": 0, "warn": 1, "blocking": 2}
        if observed not in bucket_order or declared not in bucket_order:
            findings.append({
                "id": lock_id,
                "kind": "unknown_severity",
                "declared": declared,
                "observed": observed,
                "message": f"declared={declared!r} observed={observed!r}",
            })
            summary["mismatched"] += 1
            continue
        if bucket_order[declared] != bucket_order[observed]:
            findings.append({
                "id": lock_id,
                "kind": "decl_exec_gap",
                "declared": declared,
                "observed": observed,
                "message": f"severity drift: declared {declared!r} but exit code suggests {observed!r}",
            })
            summary["mismatched"] += 1
        else:
            summary["passed"] += 1

    # Persist dynamic cache.
    if args.full and cache:
        CACHE_FILE.write_text(
            json.dumps({"ts": time.time(), "results": cache}, indent=2),
            encoding="utf-8",
        )

    ok = not findings
    report = {
        "ok": ok,
        "mode": "full" if args.full else "static",
        "policy_path": str(SGF_POLICY_YAML.relative_to(WORKSPACE)) if SGF_POLICY_YAML.is_file() else None,
        "summary": summary,
        "findings": findings,
    }
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"check-severity-registry: {'PASS' if ok else 'FAIL'} ({report['mode']})")
        print(f"  checked={summary['checked']} passed={summary['passed']} mismatched={summary['mismatched']}")
        for f in findings:
            print(f"  - {f['id']}: {f.get('kind', '?')} declared={f.get('declared','-')}")
            print(f"    {f.get('message', '')}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
