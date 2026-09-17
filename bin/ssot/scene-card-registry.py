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
import importlib.util
import sys
from pathlib import Path
from types import ModuleType

REPO = Path(__file__).resolve().parents[2]
SCENES_DIR = REPO / "docs" / "scene-cards"

_LIFECYCLE_MODULE: ModuleType | None = None


def _lifecycle_module() -> ModuleType:
    global _LIFECYCLE_MODULE
    if _LIFECYCLE_MODULE is None:
        path = Path(__file__).with_name("scene-card-lifecycle.py")
        spec = importlib.util.spec_from_file_location("scene_card_lifecycle_contract", path)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"cannot load lifecycle validator: {path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _LIFECYCLE_MODULE = module
    return _LIFECYCLE_MODULE


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


def _validate_scene(scene_path: Path) -> tuple[list[str], list[str]]:
    data = _yaml_load(scene_path)
    if not data:
        return [f"{scene_path.name}: 无法解析 YAML"], []

    scene_id = data.get("scene_id", scene_path.stem)
    result = _lifecycle_module().validate_scene_card_v2(data)
    errors = [f"{scene_id}: {error}" for error in result["errors"]]
    warnings = [f"{scene_id}: {warning}" for warning in result["warnings"]]
    schema = data.get("schema")
    if schema == "scene-card/v1":
        warnings.append(f"{scene_id}: schema '{schema}' is legacy; migrate to 'scene-card/v2'")
    elif schema not in {"scene-card/v1", "scene-card/v2"}:
        errors.append(f"{scene_id}: schema must be 'scene-card/v2' (got {schema!r})")
    return errors, warnings


def validate_scene(scene_path: Path) -> list[str]:
    """Validate a scene card against the canonical lifecycle contract."""
    errors, _ = _validate_scene(scene_path)
    return errors


def scene_warnings(scene_path: Path) -> list[str]:
    """Return non-blocking compatibility warnings for a scene card."""
    _, warnings = _validate_scene(scene_path)
    return warnings


def validate_all(scenes_dir: Path = SCENES_DIR) -> tuple[int, int, dict, dict]:
    """Validate all scene cards."""
    all_errors = {}
    all_warnings = {}
    total = 0
    for scene_file in sorted(scenes_dir.glob("*.yaml")):
        total += 1
        errors, warnings = _validate_scene(scene_file)
        if errors:
            all_errors[scene_file.name] = errors
        if warnings:
            all_warnings[scene_file.name] = warnings
    return total, total - len(all_errors), all_errors, all_warnings


def main() -> int:
    parser = argparse.ArgumentParser(description="场景卡注册校验")
    parser.add_argument("--root", type=Path, default=REPO)
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--scene", help="指定场景卡 ID")
    args = parser.parse_args()
    scenes_dir = args.root / "docs" / "scene-cards"

    if args.scene:
        scene_path = scenes_dir / f"{args.scene}.yaml"
        errors = validate_scene(scene_path)
        for warning in scene_warnings(scene_path):
            print(f"[WARN] {warning}")
        if errors:
            for e in errors:
                print(f"[FAIL] {e}")
            return 1
        print(f"[PASS] {args.scene}")
        return 0

    total, valid, errors, warnings = validate_all(scenes_dir)
    print(f"验证 {total} 个场景卡: {valid} 有效, {total - valid} 无效")
    for warning_group in warnings.values():
        for warning in warning_group:
            print(f"[WARN] {warning}")
    for error_group in errors.values():
        for error in error_group:
            print(f"[FAIL] {error}")
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
