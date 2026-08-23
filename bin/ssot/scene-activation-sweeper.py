#!/usr/bin/env python3
"""Scene Activation Sweeper — 场景激活巡检器.

巡检所有 scene-cards, 检测并尝试解决 activation_blockers,
输出可自动激活的场景列表.

用法:
    python3 scene-activation-sweeper.py              # 巡检报告
    python3 scene-activation-sweeper.py --json        # JSON 输出
    python3 scene-activation-sweeper.py --auto-fix    # 尝试自动修复
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCENE_DIR = REPO / "docs/scene-cards"


def load_scene_cards() -> list[dict]:
    """加载所有 scene cards."""
    scenes = []
    if not SCENE_DIR.exists():
        return scenes

    for f in sorted(SCENE_DIR.glob("*.yaml")):
        try:
            import yaml
            text = f.read_text()
            # 支持 frontmatter 和纯 YAML 两种格式
            fm = None
            if text.startswith("---"):
                end = text.find("---", 3)
                if end > 0:
                    fm = yaml.safe_load(text[3:end])
            if fm is None:
                # 尝试直接解析
                fm = yaml.safe_load(text)
            if fm and isinstance(fm, dict):
                fm["_file"] = str(f.relative_to(REPO))
                scenes.append(fm)
        except Exception:
            continue

    return scenes


def can_auto_activate(scene: dict) -> tuple[bool, list[str], list[str]]:
    """判断场景是否可以自动激活.

    返回: (can_activate, resolvable_blockers, unresolvable_blockers)
    """
    blockers = scene.get("activation_blockers", [])
    approval = scene.get("approval_state", "")
    lifecycle = scene.get("lifecycle", "draft")

    resolvable = []
    unresolvable = []

    for blocker in blockers:
        # 检查是否是可自动解决的 blocker
        if blocker in ("OMO_admission_evidence",):
            # 需要人工确认的工具, 不可自动解决
            unresolvable.append(blocker)
        elif blocker.startswith("calibration_below_"):
            # 校准指标不足, 需要实际运行数据
            unresolvable.append(blocker)
        elif blocker.startswith("recall_citation_rate_below_"):
            # 召回率不足, 需要实际运行数据
            unresolvable.append(blocker)
        elif blocker == "admission_provider_unavailable_in_production":
            # 生产环境不可用, 需人工介入
            unresolvable.append(blocker)
        else:
            # 其他 blocker 标记为需人工审查
            unresolvable.append(blocker)

    # 检查 approval_state
    if approval == "pending_business_confirmation":
        unresolvable.append("pending_business_confirmation")
    elif approval in ("confirmed", "approved"):
        pass  # OK

    can_activate = len(unresolvable) == 0 and len(resolvable) == 0
    return can_activate, resolvable, unresolvable


def generate_report(scenes: list[dict]) -> dict:
    """生成巡检报告."""
    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_scenes": len(scenes),
        "by_lifecycle": {},
        "by_activation": {},
        "activatable": [],
        "blocked": [],
        "needs_attention": [],
    }

    for scene in scenes:
        lifecycle = scene.get("lifecycle", "draft")
        activation = scene.get("activation", "unknown")
        scene_id = scene.get("scene_id", scene.get("title", "?"))

        # 统计 lifecycle
        report["by_lifecycle"][lifecycle] = report["by_lifecycle"].get(lifecycle, 0) + 1
        report["by_activation"][activation] = report["by_activation"].get(activation, 0) + 1

        # 检查是否可激活
        can_activate, resolvable, unresolvable = can_auto_activate(scene)

        if can_activate:
            report["activatable"].append({
                "scene_id": scene_id,
                "lifecycle": lifecycle,
                "activation": activation,
            })
        elif unresolvable:
            report["blocked"].append({
                "scene_id": scene_id,
                "lifecycle": lifecycle,
                "blockers": unresolvable,
            })
        else:
            report["needs_attention"].append({
                "scene_id": scene_id,
                "lifecycle": lifecycle,
                "resolvable": resolvable,
            })

    return report


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Scene Activation Sweeper")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    scenes = load_scene_cards()
    report = generate_report(scenes)

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return

    print("=" * 56)
    print("  Scene Activation Sweeper Report")
    print("=" * 56)
    print(f"  Total scenes: {report['total_scenes']}")
    print()

    print("  By Lifecycle:")
    for tier, count in sorted(report["by_lifecycle"].items()):
        print(f"    {tier:12s}: {count}")

    print()
    print("  By Activation:")
    for status, count in sorted(report["by_activation"].items()):
        print(f"    {status:12s}: {count}")

    if report["activatable"]:
        print()
        print(f"  ✓ Activatable ({len(report['activatable'])}):")
        for s in report["activatable"]:
            print(f"    - {s['scene_id']} ({s['lifecycle']})")

    if report["blocked"]:
        print()
        print(f"  ✗ Blocked ({len(report['blocked'])}):")
        for s in report["blocked"]:
            print(f"    - {s['scene_id']}: {', '.join(s['blockers'])}")

    if report["needs_attention"]:
        print()
        print(f"  ⚠ Needs Attention ({len(report['needs_attention'])}):")
        for s in report["needs_attention"]:
            print(f"    - {s['scene_id']}")


if __name__ == "__main__":
    sys.exit(main())
