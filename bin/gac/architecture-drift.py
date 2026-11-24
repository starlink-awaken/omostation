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


def registered_ids(registry_dir: Path) -> set[str]:
    """登记面自己说谁是已登记 —— 不在这里按分类目录猜。

    原实现只找 `registry/governance/<stem>.yaml`，于是登记在 `state/` `knowledge/`
    `workflow/` 等分类下的脚本全被报成「未注册」（2026-11-24 实测 4 条误报：
    `check-project-health-freshness.py` / `check-adr-iteration-rate.py` /
    `check-silent-workflows.py` / `health-trend-predictor.py`，四条都在别的分类下）。
    判据的来源必须是登记面本身 —— 与 `script-registry validate` 同一个集合。
    """
    import yaml

    ids: set[str] = set()
    for entry in registry_dir.rglob("*.yaml"):
        try:
            data = yaml.safe_load(entry.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001 — 单条坏条目不该让整次扫描崩
            continue
        if isinstance(data, dict) and data.get("id"):
            ids.add(str(data["id"]))
    return ids


def check_registry_drift() -> list[str]:
    """Check registry completeness."""
    warnings: list[str] = []
    registry_dir = REPO / "bin" / "_registry" / "scripts"
    if not registry_dir.exists():
        return warnings

    registered = registered_ids(registry_dir)

    gac_dir = REPO / "bin" / "gac"
    if gac_dir.exists():
        for f in gac_dir.glob("*.py"):
            if f.name.startswith("_"):
                continue
            if f"bin/gac/{f.name}" not in registered:
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
