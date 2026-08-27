#!/usr/bin/env python3
"""Automatically detect and update stale documentation."""

import json
import sys
import time
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
GENERATED_DOCS = WORKSPACE / "docs/generated"
DEFAULT_THRESHOLD_DAYS = 7


def check_stale_docs(docs_dir: Path = GENERATED_DOCS, threshold_days: int = DEFAULT_THRESHOLD_DAYS) -> list[dict]:
    stale: list[dict] = []
    if not docs_dir.exists():
        return stale
    now = time.time()
    for f in docs_dir.rglob("*"):
        if f.is_file():
            age_days = (now - f.stat().st_mtime) / 86400
            if age_days > threshold_days:
                stale.append({"file": str(f.relative_to(WORKSPACE)), "age_days": round(age_days, 1)})
    return stale


def generate_update_plan(stale_docs: list[dict]) -> list[dict]:
    plan: list[dict] = []
    for item in stale_docs:
        ext = Path(item["file"]).suffix.lower()
        if ext in (".yaml", ".yml", ".json"):
            action = "regenerate"
        elif ext == ".md":
            action = "review-and-refresh"
        else:
            action = "review"
        plan.append({"file": item["file"], "action": action, "reason": f"stale by {item['age_days']} days"})
    return plan


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Doc auto-update detector")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--threshold", type=int, default=DEFAULT_THRESHOLD_DAYS)
    args = parser.parse_args()

    stale = check_stale_docs(threshold_days=args.threshold)
    plan = generate_update_plan(stale)

    if args.json:
        print(json.dumps({"stale": stale, "plan": plan}, indent=2))
    else:
        print("=== Stale Documentation ===")
        for item in stale:
            print(f"  {item['file']}: {item['age_days']} days old")
        print(f"\nTotal: {len(stale)} stale files")
        if plan:
            print("\n=== Update Plan ===")
            for item in plan:
                print(f"  {item['file']}: {item['action']}")

    return 1 if stale else 0


if __name__ == "__main__":
    sys.exit(main())
