#!/usr/bin/env python3
"""Check submodule pin consistency for critical fix commits.

Verifies that local working trees match expected commits for submodules
that contain critical fixes (e.g., PEP degraded mode bypass).
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PinRule:
    submodule: str
    expected_commit: str
    description: str


RULES: tuple[PinRule, ...] = (
    PinRule(
        submodule="projects/agora",
        expected_commit="0b51e6b",
        description="PEP degraded mode bypass when pdp provider unavailable",
    ),
)


def run(cmd: list[str], cwd: str | None = None) -> str:
    result = subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def check_rule(rule: PinRule, root: str) -> tuple[bool, str]:
    submodule_path = Path(root) / rule.submodule
    if not submodule_path.exists():
        return False, f"missing: {submodule_path}"

    head = run(["git", "rev-parse", "HEAD"], cwd=str(submodule_path))
    if not head:
        return False, "unreadable HEAD"

    if head.startswith(rule.expected_commit) or rule.expected_commit.startswith(head):
        return True, f"HEAD={head[:12]}"
    return False, f"HEAD={head[:12]} expected={rule.expected_commit[:12]} ({rule.description})"


def main() -> int:
    parser = argparse.ArgumentParser(description="Check submodule pin consistency")
    parser.add_argument(
        "--root",
        type=str,
        default="",
        help="Repository root (default: auto-detect from script location)",
    )
    parser.add_argument(
        "--submodule",
        type=str,
        default="",
        help="Check only this submodule path",
    )
    args = parser.parse_args()

    root = args.root or str(Path(__file__).resolve().parent.parent.parent.parent.parent)
    if not (Path(root) / "pyproject.toml").exists():
        root = os.getcwd()

    rules = RULES
    if args.submodule:
        rules = tuple(r for r in rules if r.submodule == args.submodule)
        if not rules:
            print(f"No pin rules for submodule: {args.submodule}")
            return 2

    failures: list[str] = []
    for rule in rules:
        ok, detail = check_rule(rule, root)
        status = "OK" if ok else "FAIL"
        print(f"[{status}] {rule.submodule}: {detail}")
        if not ok:
            failures.append(rule.submodule)

    if failures:
        print(f"\nFAIL: {len(failures)} submodule pin(s) inconsistent: {failures}")
        return 1
    print("\nOK: all submodule pins consistent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
