#!/usr/bin/env python3
"""GaC #37 — Debt Items Integrity Check.

Verifies that all seed_items referenced in debt.yaml actually exist on disk.
Exit 1 if any file is missing.
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

    missing: list[str] = []
    for ref in seed_items:
        item_path = WORKSPACE / ref
        if not item_path.exists():
            missing.append(ref)

    if missing:
        print("[DEBT-INTEGRITY] ❌ Missing debt item files:")
        for ref in missing:
            print(f"  - {ref}")
        return 1

    print(f"[DEBT-INTEGRITY] ✅ All {len(seed_items)} seed items exist on disk")
    return 0


if __name__ == "__main__":
    sys.exit(main())
