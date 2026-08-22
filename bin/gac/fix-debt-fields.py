#!/usr/bin/env python3
"""fix-debt-fields.py — 修复 debt YAML 字段冲突."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

WORKSPACE = Path(__file__).resolve().parents[2]


def scan_debt_items(root: Path) -> tuple[list[dict], list[dict]]:
    items_dir = root / ".omo" / "debt" / "items"
    conflicts: list[dict] = []
    placeholders: list[dict] = []
    if not items_dir.is_dir():
        return conflicts, placeholders
    for path in sorted(items_dir.glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        item_id = data.get("id", path.stem)
        if "status" in data and "lifecycle_state" in data:
            conflicts.append(
                {
                    "id": item_id,
                    "path": str(path),
                    "has_status": True,
                    "has_lifecycle_state": True,
                }
            )
        for field in ["closed_evidence", "resolution_evidence"]:
            value = str(data.get(field, ""))
            if "<pending>" in value:
                placeholders.append(
                    {
                        "id": item_id,
                        "path": str(path),
                        "field": field,
                        "value": value[:120],
                    }
                )
    return conflicts, placeholders


def fix_debt_items(root: Path, apply: bool) -> dict:
    conflicts, placeholders = scan_debt_items(root)
    report = {
        "conflict_count": len(conflicts),
        "conflicts": conflicts,
        "placeholder_count": len(placeholders),
        "placeholders": placeholders,
        "applied": [],
    }
    if apply:
        items_dir = root / ".omo" / "debt" / "items"
        for conflict in conflicts:
            path = Path(conflict["path"])
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            data.pop("status", None)
            path.write_text(
                yaml.dump(data, allow_unicode=True, default_flow_style=False, sort_keys=False),
                encoding="utf-8",
            )
            report["applied"].append({"path": str(path), "action": "removed_status"})
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fix debt YAML field conflicts")
    parser.add_argument("--root", type=Path, default=WORKSPACE)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)

    if args.apply:
        report = fix_debt_items(args.root, apply=True)
    else:
        conflicts, placeholders = scan_debt_items(args.root)
        report = {
            "conflict_count": len(conflicts),
            "conflicts": conflicts,
            "placeholder_count": len(placeholders),
            "placeholders": placeholders,
            "applied": [],
        }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
