#!/usr/bin/env python3
"""Suggest (and optionally claim) the next free ADR number on origin/main.

Prevents concurrent agents from colliding on the same ADR-NNNN (2026-07-15 0195 lesson).

Usage:
  python3 bin/adr/next-adr-id.py
  python3 bin/adr/next-adr-id.py --session enforce-0203
  python3 bin/adr/next-adr-id.py --session enforce-0203 --claim
  python3 bin/adr/next-adr-id.py --json

Claim files: .omo/_delivery/adr-claims/<session>.json (runtime; not for long-lived SSOT).
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DECISIONS = ROOT / ".omo" / "_knowledge" / "decisions"
CLAIMS_DIR = ROOT / ".omo" / "_delivery" / "adr-claims"
ADR_RE = re.compile(r"^(\d{4})-.*\.md$")


def listed_numbers() -> set[int]:
    nums: set[int] = set()
    if not DECISIONS.is_dir():
        return nums
    for path in DECISIONS.iterdir():
        match = ADR_RE.match(path.name)
        if match:
            nums.add(int(match.group(1)))
    return nums


def claimed_numbers() -> dict[int, dict]:
    claimed: dict[int, dict] = {}
    if not CLAIMS_DIR.is_dir():
        return claimed
    for path in CLAIMS_DIR.glob("*.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        number = payload.get("number")
        if isinstance(number, int):
            claimed[number] = payload
    return claimed


def next_free(existing: set[int], claimed: dict[int, dict]) -> int:
    taken = set(existing) | set(claimed)
    candidate = (max(taken) + 1) if taken else 1
    while candidate in taken:
        candidate += 1
    return candidate


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session", default="", help="session / worktree name for claim file")
    parser.add_argument(
        "--claim",
        action="store_true",
        help="write short-lived claim under .omo/_delivery/adr-claims/",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    existing = listed_numbers()
    claimed = claimed_numbers()
    number = next_free(existing, claimed)
    # Prefer origin/main tip if available (advisory only)
    try:
        subprocess.run(
            ["git", "fetch", "origin", "main"],
            cwd=ROOT,
            capture_output=True,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        pass

    result = {
        "next": number,
        "next_id": f"{number:04d}",
        "existing_max": max(existing) if existing else 0,
        "claimed_count": len(claimed),
        "session": args.session or None,
        "claim_path": None,
    }

    if args.claim:
        if not args.session:
            print("error: --claim requires --session", file=sys.stderr)
            return 2
        CLAIMS_DIR.mkdir(parents=True, exist_ok=True)
        claim_path = CLAIMS_DIR / f"{args.session}.json"
        payload = {
            "number": number,
            "next_id": f"{number:04d}",
            "session": args.session,
            "claimed_at": datetime.now(UTC).isoformat(),
            "note": "short-lived; release by deleting this file after ADR lands on main",
        }
        claim_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        result["claim_path"] = str(claim_path.relative_to(ROOT))
        result["claimed"] = True

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        line = f"ADR-{result['next_id']}"
        if args.session:
            line += f" (session={args.session})"
        if result.get("claim_path"):
            line += f" claimed → {result['claim_path']}"
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
