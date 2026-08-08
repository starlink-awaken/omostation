#!/usr/bin/env python3
"""check-subtraction-quota: 增 1 删 1 门禁 (BET-Y1Q2-T6-05).

PR 新增 GaC 规则必须同时删除一条; 新增 ADR 必须同时归档一份.
例外: SWARM_ESCAPE_ID=subtraction-quota.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]


def _staged_changes() -> list[tuple[str, str]]:
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-status", "--diff-filter=AD"],
        cwd=WORKSPACE, capture_output=True, text=True,
    )
    if result.returncode != 0:
        return []
    lines = []
    for line in result.stdout.strip().split("\n"):
        if not line:
            continue
        parts = line.split("\t", 1)
        if len(parts) == 2:
            lines.append((parts[0], parts[1]))
    return lines


def main() -> int:
    if "subtraction-quota" in os.environ.get("SWARM_ESCAPE_ID", ""):
        print("[subtraction-quota] BYPASS (SWARM_ESCAPE_ID)")
        return 0

    changes = _staged_changes()
    if not changes:
        print("[subtraction-quota] no staged changes — PASS")
        return 0

    rule_pat = re.compile(r"projects/ecos/.*/GAC-RULE-.*\.yaml$")
    adr_pat = re.compile(r"\.omo/_knowledge/decisions/\d{4}-.*\.md$")

    rule_a = sum(1 for s, p in changes if s == "A" and rule_pat.match(p))
    rule_d = sum(1 for s, p in changes if s == "D" and rule_pat.match(p))
    adr_a = sum(1 for s, p in changes if s == "A" and adr_pat.match(p))
    adr_d = sum(1 for s, p in changes if s == "D" and adr_pat.match(p))

    ok = True
    if rule_a > rule_d:
        print(f"[subtraction-quota] FAIL: GaC rules +{rule_a} -{rule_d} (增1删1 violated)")
        ok = False
    if adr_a > adr_d:
        print(f"[subtraction-quota] FAIL: ADRs +{adr_a} -{adr_d} (增1删1 violated)")
        ok = False

    if ok:
        print(f"[subtraction-quota] PASS: rules +{rule_a}/-{rule_d}, ADRs +{adr_a}/-{adr_d}")
        return 0

    print("[subtraction-quota] 增 1 删 1 — 例外: SWARM_ESCAPE_ID=subtraction-quota")
    return 1


if __name__ == "__main__":
    sys.exit(main())
