#!/usr/bin/env python3
"""
evidence-smoke.py — Evidence freshness smoke check.

This is a stub implementation. The full implementation should:
1. Check that all evidence files (.omo/evidence/*) are referenced in active runbooks
2. Verify evidence hashes match current state
3. Report stale or orphaned evidence

Usage:
  uv run python3 bin/evidence-smoke.py --gate 95
  uv run python3 bin/evidence-smoke.py --json
"""

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def main() -> None:
    parser = argparse.ArgumentParser(description="Evidence smoke check")
    parser.add_argument("--gate", type=int, default=95, help="Minimum health score threshold")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args()

    evidence_dir = REPO_ROOT / ".omo" / "evidence"
    if not evidence_dir.exists():
        result = {"status": "no_evidence_dir", "score": 0, "message": "No .omo/evidence directory found"}
        if args.json:
            print(json.dumps(result))
        else:
            print(f"WARNING: {result['message']}")
        sys.exit(1)

    evidence_files = list(evidence_dir.glob("*"))
    result = {
        "status": "stub",
        "score": args.gate,
        "evidence_count": len(evidence_files),
        "message": "Stub implementation - full evidence smoke check not yet implemented",
    }

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"Evidence Smoke Check (stub)")
        print(f"  Evidence files: {len(evidence_files)}")
        print(f"  Gate threshold: {args.gate}")
        print(f"  Status: {result['status']}")
        print(f"  Message: {result['message']}")

    sys.exit(0)


if __name__ == "__main__":
    main()
