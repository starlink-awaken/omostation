#!/usr/bin/env python3
"""GaC #37 — Debt Items Integrity Check.

Bidirectional integrity between debt.yaml's seed_items and the items dir:

  forward  seed_items → disk     (a registered item must exist)
  reverse  items dir → seed_items (an existing item must be registered)

The reverse direction is load-bearing: an item file that is never seeded is
invisible to `load_debt_ledger` — it drops out of the dashboard, the metrics,
the review queue and the action packet silently. 2026-11-09 实测: 21 files
were orphaned this way, including 7 `identified` (high/medium) and 1
`in_progress` — i.e. live debt with overdue reviews and zero visibility.

Exit 1 if either direction fails.
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

WORKSPACE = Path(__file__).resolve().parents[2]
DEBT_REGISTRY = WORKSPACE / ".omo" / "_truth" / "registry" / "debt.yaml"


def main() -> int:
    if not DEBT_REGISTRY.exists():
        print(f"[DEBT-INTEGRITY] ⚠️  Debt registry not found at {DEBT_REGISTRY}")
        return 1

    registry = yaml.safe_load(DEBT_REGISTRY.read_text())
    seed_items: list[str] = registry.get("seed_items", [])

    if not seed_items:
        print("[DEBT-INTEGRITY] ❌ No seed_items in debt registry — debt system is empty")
        return 1

    failed = False

    missing: list[str] = []
    for ref in seed_items:
        item_path = WORKSPACE / ref
        if not item_path.exists():
            missing.append(ref)

    if missing:
        failed = True
        print("[DEBT-INTEGRITY] ❌ Missing debt item files (registered but absent):")
        for ref in missing:
            print(f"  - {ref}")

    # Reverse direction: every *.yaml in items_dir must be registered.
    # Without this, an item created but never seeded is silently dropped from
    # the ledger — no metric, no review queue entry, no escalation.
    items_dir = WORKSPACE / str(registry.get("items_dir") or ".omo/debt/items")
    if items_dir.is_dir():
        seeded = set(seed_items)
        orphans = sorted(
            str(p.relative_to(WORKSPACE))
            for p in items_dir.glob("*.yaml")
            if p.relative_to(WORKSPACE).as_posix() not in seeded
        )
        if orphans:
            failed = True
            print(
                "[DEBT-INTEGRITY] ❌ Orphan debt item files (present but not registered "
                "in seed_items — invisible to the ledger):"
            )
            for ref in orphans:
                print(f"  - {ref}")

    if failed:
        return 1

    print(
        f"[DEBT-INTEGRITY] ✅ All {len(seed_items)} seed items exist on disk and "
        "every items/*.yaml is registered"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
