#!/usr/bin/env python3
"""scene-card-lifecycle.py — 场景卡生命周期管理工具."""

from __future__ import annotations
import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCENES_DIR = REPO / "docs" / "scene-cards"

LIFECYCLE_LEVELS = ["draft", "shadow", "assisted", "supervised", "routine"]
ACTIVATIONS = {"preview", "controlled", "active"}


def _yaml_load(path: Path) -> dict:
    try:
        import yaml
        text = path.read_text(encoding="utf-8")
        docs = list(yaml.safe_load_all(text))
        result = {}
        for doc in docs:
            if isinstance(doc, dict):
                result.update(doc)
        return result
    except Exception:
        return {}


def validate_scene(scene_path: Path) -> list[str]:
    errors = []
    data = _yaml_load(scene_path)
    if not data:
        return [f"{scene_path.name}: 无法解析 YAML"]
    scene_id = data.get("scene_id", scene_path.stem)
    lifecycle = data.get("lifecycle", "")
    activation = data.get("activation", "")
    if lifecycle not in LIFECYCLE_LEVELS:
        errors.append(f"{scene_id}: lifecycle '{lifecycle}' 无效")
    if activation not in ACTIVATIONS:
        errors.append(f"{scene_id}: activation '{activation}' 无效")
    return errors


def validate_all():
    all_errors = {}
    total = 0
    for f in sorted(SCENES_DIR.glob("*.yaml")):
        total += 1
        errors = validate_scene(f)
        if errors:
            all_errors[f.name] = errors
    return total, total - len(all_errors), all_errors


def show_status():
    levels = {}
    for f in sorted(SCENES_DIR.glob("*.yaml")):
        data = _yaml_load(f)
        lc = data.get("lifecycle", "unknown")
        levels[lc] = levels.get(lc, 0) + 1
    print("场景卡生命周期状态")
    print("=" * 50)
    for lv in LIFECYCLE_LEVELS:
        c = levels.get(lv, 0)
        print(f"  {lv:12s}: {c:3d} {'█' * c}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="场景卡生命周期管理")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--scene", help="场景卡 ID")
    parser.add_argument("--status", action="store_true")
    args = parser.parse_args()

    if args.status:
        return show_status()
    if args.scene:
        errors = validate_scene(SCENES_DIR / f"{args.scene}.yaml")
        if errors:
            for e in errors:
                print(f"[FAIL] {e}")
            return 1
        print(f"[PASS] {args.scene}")
        return 0

    total, valid, errors = validate_all()
    print(f"验证 {total} 个场景卡: {valid} 有效, {total - valid} 无效")
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
