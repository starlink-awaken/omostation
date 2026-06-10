#!/usr/bin/env python3
"""Update x2_freshness on all open debt items.

This is the X2 freshness enforcement mechanism. Run as cron to keep
freshness metadata current (recommended: every 30 minutes).

Usage: python3 scripts/update_debt_freshness.py [--omo-dir PATH]
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

# Add src/ to path so the package is importable from the repo root
_src = Path(__file__).resolve().parent.parent / "src"
if str(_src) not in sys.path:
    sys.path.insert(0, str(_src))

from omo.omo_io import write_yaml_atomic


def _utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _is_open(state: str) -> bool:
    """Return True if the item is in an active (non-closed) lifecycle state."""
    return state in ("identified", "open", "in_progress", "scheduled")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Update x2_freshness on all open debt items."
    )
    parser.add_argument(
        "--omo-dir",
        default=".omo",
        help="Path to .omo directory (default: .omo)",
    )
    args = parser.parse_args()

    omo_dir = Path(args.omo_dir)
    registry_path = omo_dir / "debt" / "registry.yaml"

    if not registry_path.exists():
        print(f"Registry not found at {registry_path}")
        return 1

    registry = _load_yaml(registry_path)
    seed_items: list[str] = registry.get("seed_items", [])
    now = _utc_now()
    updated = 0
    skipped = 0
    errors = 0

    for seed_ref in seed_items:
        # seed_ref is like ".omo/debt/items/DEBT-OMO-001.yaml"
        # omo_dir is Path(".omo"), so omo_dir.parent is Path(".")
        item_path = (
            omo_dir.parent / seed_ref
            if seed_ref.startswith(".omo")
            else Path(seed_ref)
        )

        if not item_path.exists():
            print(f"  SKIP  {seed_ref} — file not found")
            skipped += 1
            continue

        try:
            payload = _load_yaml(item_path)
        except Exception as exc:
            print(f"  ERROR {seed_ref} — {exc}")
            errors += 1
            continue

        state = payload.get("lifecycle_state", "")
        if not _is_open(state):
            skipped += 1
            continue

        payload["x2_freshness"] = now
        write_yaml_atomic(item_path, payload)
        updated += 1

    print(f"Updated freshness on {updated} open debt items at {now}")
    if skipped:
        print(f"  Skipped: {skipped} (closed/non-active items)")
    if errors:
        print(f"  Errors: {errors}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
