#!/usr/bin/env python3
"""scene-card-registry.py — 场景卡注册校验.

注册场景卡时自动校验架构合规:
- lifecycle 5 级
- domain 5 域
- promotion_evidence 必填

用法:
    python3 bin/ssot/scene-card-registry.py --validate --all
    python3 bin/ssot/scene-card-registry.py --validate --scene <scene_id>
"""

from __future__ import annotations
import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCENES_DIR = REPO / "docs" / "scene-cards"

VALID_LIFECYCLES = ["draft", "shadow", "assisted", "supervised", "routine"]
VALID_DOMAINS = ["work", "health", "research", "knowledge", "governance"]


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
    """Validate a scene card."""
    errors = []
    data = _yaml_load(scene_path)
    if not data:
        return [f"{scene_path.name}: 无法解析 YAML"]

    scene_id = data.get("scene_id", scene_path.stem)

    # 1. lifecycle
    lifecycle = data.get("lifecycle", "")
    if lifecycle and lifecycle not in VALID_LIFECYCLES:
        errors.append(f"{scene_id}: lifecycle '{lifecycle}' 无效 {VALID_LIFECYCLES}")

    # 2. domain
    domain = data.get("domain", "")
    if not domain:
        errors.append(f"{scene_id}: 缺少 domain 字段")
    elif domain not in VALID_DOMAINS:
        errors.append(f"{scene_id}: domain '{domain}' 无效 {VALID_DOMAINS}")

    # 3. promotion evidence
    if lifecycle in ["assisted", "supervised", "routine"]:
        if not data.get("promotion_evidence"):
            errors.append(f"{scene_id}: 升级到 {lifecycle} 需要 promotion_evidence")

    return errors


def validate_all() -> tuple[int, int, dict]:
    """Validate all scene cards."""
    all_errors = {}
    total = 0
    for scene_file in sorted(SCENES_DIR.glob("*.yaml")):
        total += 1
        errors = validate_scene(scene_file)
        if errors:
            all_errors[scene_file.name] = errors
    return total, total - len(all_errors), all_errors


def main() -> int:
    parser = argparse.ArgumentParser(description="场景卡注册校验")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--scene", help="指定场景卡 ID")
    args = parser.parse_args()

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
