#!/usr/bin/env python3
"""Suggest (and atomically claim) the next free ADR number.

G-CONV.7 / ADR-0220 D1: claims use exclusive flock via swarm_discipline so
concurrent agents cannot double-allocate the same ADR-NNNN.

Usage:
  python3 bin/adr/next-adr-id.py
  python3 bin/adr/next-adr-id.py --session enforce-0203
  python3 bin/adr/next-adr-id.py --session enforce-0203 --claim
  python3 bin/adr/next-adr-id.py --json
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "bin" / "gac"))
import swarm_discipline as sd  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session", default="", help="session / worktree name for claim file")
    parser.add_argument(
        "--claim",
        action="store_true",
        help="atomically claim next free number under .omo/_delivery/adr-claims/",
    )
    parser.add_argument(
        "--number",
        type=int,
        default=None,
        help="optional specific number to claim (must be free)",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

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

    existing = sd.list_existing_adr_numbers(ROOT / ".omo" / "_knowledge" / "decisions")
    claimed = sd.load_adr_claims(
        sd.delivery_path(ROOT, "adr_claims_dir", ".omo/_delivery/adr-claims")
    )

    if args.claim:
        if not args.session:
            print("error: --claim requires --session", file=sys.stderr)
            return 2
        ok, result = sd.acquire_adr_claim(ROOT, args.session, number=args.number)
        if not ok:
            if args.json:
                print(json.dumps({"ok": False, **result}, ensure_ascii=False, indent=2))
            else:
                print(f"error: {result.get('error')}", file=sys.stderr)
            return 1
        result_out = {
            "ok": True,
            "next": result["number"],
            "next_id": result["next_id"],
            "existing_max": max(existing) if existing else 0,
            "claimed_count": len(claimed) + (0 if result.get("reused") else 1),
            "session": args.session,
            "claim_path": result.get("claim_path"),
            "claimed": True,
            "reused": result.get("reused"),
            "gate": "d1_adr_atomic_claim",
        }
        if args.json:
            print(json.dumps(result_out, ensure_ascii=False, indent=2))
        else:
            line = f"ADR-{result_out['next_id']} (session={args.session})"
            line += f" claimed → {result_out['claim_path']}"
            if result.get("reused"):
                line += " [reused]"
            print(line)
        return 0

    # advisory suggest (no lock) — prefer claim for real work
    number = args.number or sd.next_free_adr(existing, claimed)
    result = {
        "next": number,
        "next_id": f"{number:04d}",
        "existing_max": max(existing) if existing else 0,
        "claimed_count": len(claimed),
        "session": args.session or None,
        "claim_path": None,
        "claimed": False,
        "note": "advisory only; use --claim for D1 atomic occupation",
    }
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        line = f"ADR-{result['next_id']}"
        if args.session:
            line += f" (session={args.session})"
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
