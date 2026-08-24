#!/usr/bin/env python3
"""Shadow Reporter — Shadow 场景观察报告器."""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCENE_DIR = REPO / "docs/scene-cards"


def load_scene_cards() -> list[dict]:
    scenes = []
    if not SCENE_DIR.exists():
        return scenes
    for f in sorted(SCENE_DIR.glob("*.yaml")) + sorted(SCENE_DIR.glob("v2/*.yaml")):
        try:
            import yaml
            text = f.read_text()
            fm = {}
            for part in text.split("---"):
                part = part.strip()
                if not part:
                    continue
                try:
                    data = yaml.safe_load(part)
                    if isinstance(data, dict):
                        fm.update(data)
                except Exception:
                    pass
            if fm and isinstance(fm, dict):
                fm["_file"] = str(f.relative_to(REPO))
                scenes.append(fm)
        except Exception:
            continue
    return scenes


def generate_shadow_report(scene: dict) -> dict:
    scene_id = scene.get("scene_id", scene.get("title", "?"))
    lifecycle = scene.get("lifecycle", "draft")
    blockers = scene.get("activation_blockers", [])
    approval = scene.get("approval_state", "")
    readiness = "ready" if not blockers and approval == "confirmed" else "blocked"
    if approval == "pending_business_confirmation":
        readiness = "needs_approval"
    return {
        "scene_id": scene_id,
        "lifecycle": lifecycle,
        "activation": scene.get("activation", "?"),
        "approval_state": approval,
        "blockers": blockers,
        "readiness": readiness,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Shadow Reporter")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--scene", help="Report specific scene")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    scenes = load_scene_cards()
    shadow_scenes = [s for s in scenes if s.get("lifecycle") == "shadow"]
    if args.scene:
        shadow_scenes = [s for s in shadow_scenes if args.scene in s.get("scene_id", "")]
    reports = [generate_shadow_report(s) for s in shadow_scenes]

    if args.json:
        print(json.dumps(reports, ensure_ascii=False, indent=2))
        return

    print("=" * 56)
    print("  Shadow Scene Observation Reports")
    print("=" * 56)
    print(f"  Shadow scenes: {len(reports)}")
    print()
    for r in reports:
        icon = "✓" if r["readiness"] == "ready" else "⚠" if r["readiness"] == "needs_approval" else "✗"
        print(f"  {icon} {r['scene_id']}")
        print(f"      Readiness: {r['readiness']}")
        if r["blockers"]:
            print(f"      Blockers: {', '.join(r['blockers'])}")


if __name__ == "__main__":
    sys.exit(main())
