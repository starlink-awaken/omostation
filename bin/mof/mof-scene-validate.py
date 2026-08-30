#!/usr/bin/env python3
"""mof-scene-validate.py — 场景卡 MOF 架构约束验证器.

验证场景卡 YAML 符合 MOF 架构约束:
- SFOP 槽位分配正确性
- 道法术器分层一致性
- BOS URI 域分类
- 治理规则引用存在性

用法:
    python3 bin/mof/mof-scene-validate.py --all
    python3 bin/mof/mof-scene-validate.py --scene documents-weijian-cleanup
    python3 bin/mof/mof-scene-validate.py --json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCENES_DIR = REPO / "docs" / "scene-cards"
MOF_M1_DIR = REPO / "projects" / "ecos" / "src" / "ecos" / "ssot" / "mof" / "m1"

VALID_LIFECYCLES = {"draft", "shadow", "assisted", "supervised", "routine"}
VALID_ACTIVATIONS = {"preview", "controlled", "active"}
VALID_SLOTS = {"K", "H", "P", "C", "S", "B", "J", "O", "F"}
VALID_LAYERS = {"dao", "fa", "shu", "qi"}
VALID_BOS_PREFIXES = (
    "bos://memory/", "bos://governance/", "bos://analysis/",
    "bos://persona/", "bos://capability/",
)
SCENE_ID_PATTERN = re.compile(r"^(scene|documents)-[a-z0-9-]+$")


def _yaml_load(path: Path) -> dict:
    """Load YAML file, handling multi-document streams."""
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


def _load_m1_specifications() -> set[str]:
    """Load all M1 specification node IDs."""
    specs = set()
    if not MOF_M1_DIR.exists():
        return specs
    for f in MOF_M1_DIR.rglob("*.yaml"):
        try:
            import yaml
            data = yaml.safe_load(f.read_text(encoding="utf-8"))
            if isinstance(data, dict) and "id" in data:
                specs.add(data["id"])
        except Exception:
            continue
    return specs


def validate_scene(scene_path: Path, m1_specs: set[str]) -> list[str]:
    """Validate a single scene card."""
    errors = []
    data = _yaml_load(scene_path)
    if not data:
        return [f"{scene_path.name}: 无法解析 YAML"]

    scene_id = data.get("scene_id", scene_path.stem)

    if not SCENE_ID_PATTERN.match(scene_id):
        errors.append(f"{scene_id}: scene_id 格式无效")

    lifecycle = data.get("lifecycle", "")
    if lifecycle and lifecycle not in VALID_LIFECYCLES:
        errors.append(f"{scene_id}: lifecycle '{lifecycle}' 无效")

    activation = data.get("activation", "")
    if activation and activation not in VALID_ACTIVATIONS:
        errors.append(f"{scene_id}: activation '{activation}' 无效")

    arch = data.get("architecture", {})
    if not arch:
        return errors

    bos_uri = arch.get("bos_uri", "")
    if bos_uri and not any(bos_uri.startswith(p) for p in VALID_BOS_PREFIXES):
        errors.append(f"{scene_id}: bos_uri 无效前缀")

    slot = arch.get("sfop_slot", "")
    if slot and slot not in VALID_SLOTS:
        errors.append(f"{scene_id}: sfop_slot '{slot}' 无效")

    dao_layer = arch.get("dao_layer", "")
    if dao_layer and dao_layer not in VALID_LAYERS:
        errors.append(f"{scene_id}: dao_layer '{dao_layer}' 无效")

    mof = data.get("mof", {})
    spec_ref = mof.get("specification", "")
    if spec_ref and m1_specs and spec_ref not in m1_specs:
        errors.append(f"{scene_id}: mof.specification 不存在")

    return errors


def validate_all(output_json: bool = False) -> int:
    """Validate all scene cards."""
    m1_specs = _load_m1_specifications()
    all_errors = {}
    total = 0
    for scene_file in sorted(SCENES_DIR.glob("*.yaml")):
        total += 1
        errors = validate_scene(scene_file, m1_specs)
        if errors:
            all_errors[scene_file.name] = errors

    if output_json:
        print(json.dumps({
            "total": total, "valid": total - len(all_errors),
            "invalid": len(all_errors), "errors": all_errors,
        }, ensure_ascii=False, indent=2))
    else:
        print(f"验证 {total} 个场景卡:")
        print(f"  有效: {total - len(all_errors)}")
        print(f"  无效: {len(all_errors)}")
    return 0 if not all_errors else 1


def validate_single(scene_id: str) -> int:
    """Validate a single scene card."""
    scene_path = SCENES_DIR / f"{scene_id}.yaml"
    if not scene_path.exists():
        print(f"场景卡不存在: {scene_path}", file=sys.stderr)
        return 1
    m1_specs = _load_m1_specifications()
    errors = validate_scene(scene_path, m1_specs)
    if errors:
        for e in errors:
            print(f"[FAIL] {e}")
        return 1
    print(f"[PASS] {scene_id}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="场景卡 MOF 架构约束验证器")
    parser.add_argument("--all", action="store_true", help="验证所有场景卡")
    parser.add_argument("--scene", help="验证指定场景卡")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    args = parser.parse_args()
    if args.scene:
        return validate_single(args.scene)
    return validate_all(args.json)


if __name__ == "__main__":
    sys.exit(main())
