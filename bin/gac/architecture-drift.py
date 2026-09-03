#!/usr/bin/env python3
"""architecture-drift.py — 架构漂移检测.

检测架构标准与实际运行的不一致.

用法:
    python3 bin/gac/architecture-drift.py --check
    python3 bin/gac/architecture-drift.py --json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def check_lifecycle_drift() -> list[str]:
    """Check scene card lifecycle drift."""
    warnings = []
    scenes_dir = REPO / "docs" / "scene-cards"
    if not scenes_dir.exists():
        return warnings

    for f in sorted(scenes_dir.glob("*.yaml")):
        text = f.read_text(encoding="utf-8")
        if "lifecycle: routine" in text and "promotion_evidence" not in text:
            warnings.append(f"{f.stem}: routine 缺少 promotion_evidence")

    return warnings


def check_registry_drift() -> list[str]:
    """Check registry completeness."""
    warnings = []
    registry_dir = REPO / "bin" / "_registry" / "scripts"
    if not registry_dir.exists():
        return warnings

    # Check for unregistered scripts
    gac_dir = REPO / "bin" / "gac"
    if gac_dir.exists():
        for f in gac_dir.glob("*.py"):
            if f.name.startswith("_"):
                continue
            reg_file = registry_dir / "governance" / f"{f.stem}.yaml"
            if not reg_file.exists():
                warnings.append(f"脚本未注册: {f.name}")

    return warnings


def main() -> int:
    parser = argparse.ArgumentParser(description="架构漂移检测")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    warnings = []
    warnings.extend(check_lifecycle_drift())
    warnings.extend(check_registry_drift())

    if args.json:
        print(json.dumps({"drift_count": len(warnings), "warnings": warnings}, ensure_ascii=False, indent=2))
        return 0

    if warnings:
        print(f"检测到 {len(warnings)} 个架构漂移:")
        for w in warnings[:10]:
            print(f"  ⚠️  {w}")
        return 0  # Drift is warning, not failure

    print("✅ 无架构漂移")
    return 0


if __name__ == "__main__":
    sys.exit(main())
