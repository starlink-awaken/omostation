#!/usr/bin/env python3
"""Scene v3 Batch Migration — migrate all v1/v2 cards to v3.

Usage:
  python3 bin/ssot/scene-v3-batch-migrate.py scan
  python3 bin/ssot/scene-v3-batch-migrate.py migrate [--dry-run]
  python3 bin/ssot/scene-v3-batch-migrate.py report
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT / "docs" / "scene-cards"
DST_DIR = ROOT / ".omo" / "_truth" / "scenarios" / "v3"

TIER_ACTIVATION = {
    "draft": "preview",
    "shadow": "preview",
    "assisted": "controlled",
    "supervised": "active",
    "routine": "allowed",
}

LEGACY_LIFECYCLE_MAP = {
    "proposal_only": "draft",
    "active": "routine",
    "forbidden": "draft",
}


def scan_cards() -> list[dict[str, Any]]:
    """Scan all v1/v2 scene cards."""
    import yaml
    cards = []
    if not SRC_DIR.is_dir():
        return cards
    for f in sorted(SRC_DIR.glob("*.yaml")):
        try:
            with open(f, encoding="utf-8") as fh:
                docs = list(yaml.safe_load_all(fh))
            body = docs[-1] if len(docs) > 1 else docs[0]
            if not isinstance(body, dict):
                continue
            schema = body.get("schema", "scene-card/v1")
            if schema == "scene-card/v3":
                continue
            cards.append({
                "file": str(f.relative_to(ROOT)),
                "scene_id": body.get("scene_id", f.stem),
                "schema": schema,
                "lifecycle": body.get("lifecycle", "draft"),
                "name": body.get("name", ""),
            })
        except Exception as e:
            print(f"  WARN: {f}: {e}", file=sys.stderr)
    return cards


def convert_card(body: dict[str, Any], scene_id: str) -> dict[str, Any]:
    """Convert a v1/v2 card to v3 format."""
    lifecycle = body.get("lifecycle", "draft")
    lifecycle = LEGACY_LIFECYCLE_MAP.get(lifecycle, lifecycle)

    v3 = {
        "schema": "scene-card/v3",
        "scene_id": scene_id,
        "version": "3.0.0",
        "name": body.get("name", scene_id.replace("-", " ").title()),
        "description": body.get("goal", body.get("description", "")),
        "scene_class": body.get("scene_class", "business"),
        "scene_type": body.get("scene_type", "inbound"),
        "domain": body.get("domain", "work"),
        "lifecycle": lifecycle,
        "activation": TIER_ACTIVATION.get(lifecycle, "preview"),
        "owner": body.get("owner", "governance-agent"),
        "approver": body.get("approver", "governance-agent"),
        "approval_state": body.get("approval_state", "confirmed"),
        "bet": body.get("bet", ""),
        "runtime": {
            "journey_ref": body.get("journey_id", f"journey-{scene_id}"),
            "timeout": "3600s",
            "sandbox": {
                "level": "isolated",
                "capabilities": body.get("capability_refs", []),
                "permissions": body.get("permission_scope", []),
            },
        },
        "quality": {
            "calibration": {
                "min_samples": 30,
                "min_calibration": 0.6,
                "metrics": [
                    {"name": "success_rate", "target": 0.9, "weight": 0.5},
                    {"name": "time_saved_ratio", "target": 0.5, "weight": 0.3},
                    {"name": "false_positive_rate", "target": 0.1, "weight": 0.2},
                ],
            },
        },
        "falsifier": body.get("falsifier", []),
        "observability": {"tracing": True, "evidence_capture": "full"},
        "activation_blockers": body.get("activation_blockers", []),
    }

    # Preserve extra fields
    for key in ("trigger", "input_contract", "result_contract", "outcome_metric",
                "consumer", "failure_cost", "data_classification", "data_scope",
                "operator", "permission_ref", "downstream_refs", "sample_refs"):
        if body.get(key):
            v3[key] = body[key]

    return v3


def migrate(dry_run: bool = False) -> tuple[int, int]:
    """Migrate all v1/v2 cards to v3."""
    import yaml
    cards = scan_cards()
    migrated = 0
    skipped = 0

    for card in cards:
        src_path = ROOT / card["file"]
        with open(src_path, encoding="utf-8") as f:
            docs = list(yaml.safe_load_all(f))
        body = docs[-1] if len(docs) > 1 else docs[0]
        if not isinstance(body, dict):
            skipped += 1
            continue

        scene_id = body.get("scene_id", src_path.stem)
        v3 = convert_card(body, scene_id)
        dst_path = DST_DIR / f"{scene_id}.yaml"

        if dry_run:
            print(f"  [DRY RUN] {card['file']} -> {dst_path.relative_to(ROOT)}")
            migrated += 1
            continue

        DST_DIR.mkdir(parents=True, exist_ok=True)
        with open(dst_path, "w", encoding="utf-8") as f:
            yaml.dump(v3, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
        migrated += 1
        print(f"  Migrated: {scene_id}")

    return migrated, skipped


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("scan", help="Scan v1/v2 cards")
    mp = sub.add_parser("migrate", help="Migrate to v3")
    mp.add_argument("--dry-run", action="store_true")
    sub.add_parser("report", help="Report migration status")

    args = parser.parse_args(argv)
    command = args.command or "scan"

    if command == "scan":
        cards = scan_cards()
        print(f"v1/v2 cards: {len(cards)}")
        for c in cards[:10]:
            print(f"  {c['lifecycle']:<12} {c['scene_id']:<35} {c['schema']}")

    elif command == "migrate":
        migrated, skipped = migrate(dry_run=getattr(args, "dry_run", False))
        print(f"\nMigrated: {migrated}, Skipped: {skipped}")

    elif command == "report":
        cards = scan_cards()
        v3_dir = DST_DIR
        v3_count = len(list(v3_dir.glob("*.yaml"))) if v3_dir.is_dir() else 0
        print(f"v1/v2 remaining: {len(cards)}")
        print(f"v3 migrated: {v3_count}")
        print(f"Total: {len(cards) + v3_count}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
