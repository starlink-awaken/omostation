#!/usr/bin/env python3
"""audit-principal-id-canonicalization.py — SH-7 cross-call-site audit.

Reports every place in ``bin/`` that reads ``OMO_PRINCIPAL_ID``
without routing through ``bin/ssot/_principal_id.principal_id_from_env``
(or the recorder's internal ``_canonical_principal_id``).

The audit is *advisory* — it lists call sites and labels them
CANONICAL / UNSAFE / INDIRECT so a future cleanup can target the
unsafe ones.  It does not fail the gate; that is intentional while
call-site migration is in progress.

Exit codes:
  0 — no UNSAFE sites found (clean)
  1 — at least one UNSAFE site (gate can be made strict later)
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _git_ls_tracked_bin() -> list[str]:
    """List all .py files tracked under bin/ on HEAD."""
    result = subprocess.run(
        ["git", "ls-tree", "-r", "HEAD", "--name-only", "--", "bin"],
        cwd=str(ROOT), capture_output=True, text=True, check=False,
    )
    return [
        line.strip()
        for line in result.stdout.splitlines()
        if line.strip().endswith(".py") and not line.strip().endswith("__pycache__")
    ]


def _classify(path: str, text: str) -> str:
    """Classify how a file reads OMO_PRINCIPAL_ID."""
    if "OMO_PRINCIPAL_ID" not in text:
        return "UNUSED"

    # Look for the canonical pattern: import from the shared module or
    # use the recorder's internal helper.
    canonical_patterns = [
        r"from\s+\S*_principal_id\s+import",
        r"principal_id_from_env\s*\(",
        r"_canonical_principal_id\s*\(",  # recorder's internal alias (SH-5.1)
        r"_pid\.principal_id_from_env\s*\(",
        r"_pid\.canonical_principal_id\s*\(",
    ]
    if any(re.search(p, text) for p in canonical_patterns):
        return "CANONICAL"

    # Look for direct env reads.  These are UNSAFE.
    direct_patterns = [
        r"os\.environ\.get\(\s*[\"']OMO_PRINCIPAL_ID[\"']",
        r"os\.environ\.get\(\s*'OMO_PRINCIPAL_ID'",
        r"env\.get\(\s*[\"']OMO_PRINCIPAL_ID[\"']",
        r"env\.get\(\s*'OMO_PRINCIPAL_ID'",
    ]
    if any(re.search(p, text) for p in direct_patterns):
        return "UNSAFE"

    # The string appears but in a comment / docstring / unrelated
    # context.  Flag as INDIRECT for human review.
    return "INDIRECT"


def audit() -> dict:
    findings: list[dict] = []
    for rel in _git_ls_tracked_bin():
        path = ROOT / rel
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        cls = _classify(rel, text)
        if cls == "UNUSED":
            continue
        # Locate each occurrence for human inspection.
        lines = []
        for i, line in enumerate(text.splitlines(), start=1):
            if "OMO_PRINCIPAL_ID" in line:
                lines.append({"line": i, "text": line.strip()[:160]})
        findings.append({
            "path": rel,
            "class": cls,
            "occurrences": lines,
        })
    unsafe = [f for f in findings if f["class"] == "UNSAFE"]
    return {
        "schema": "principal-id-audit/v1",
        "total_callers": len(findings),
        "unsafe_count": len(unsafe),
        "findings": findings,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true",
                        help="exit 1 when unsafe sites exist")
    args = parser.parse_args(argv)

    report = audit()
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"=== principal-id canonicalization audit (BET-Y2Q4-SH-7) ===")
        print(f"  total_callers: {report['total_callers']}")
        print(f"  unsafe_count:  {report['unsafe_count']}")
        for f in report["findings"]:
            mark = {"CANONICAL": "[OK]", "UNSAFE": "[!!]", "INDIRECT": "[?]"}.get(
                f["class"], "[?]"
            )
            print(f"\n  {mark} {f['path']}  ({f['class']})")
            for occ in f["occurrences"]:
                print(f"      L{occ['line']:>4}: {occ['text']}")
    if args.strict and report["unsafe_count"] > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())