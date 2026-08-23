#!/usr/bin/env python3
"""Scene Trigger — 信号匹配场景并触发旅程.

管线:
  signal-sources.yaml → 匹配 scene-binding → 加载 scene-card
    → 检查 activation → 匹配 journey_id → JourneyRunner.execute_journey()

用法:
    python3 bin/ssot/scene-trigger.py --list          # 列出可触发场景
    python3 bin/ssot/scene-trigger.py --status        # 场景状态概览
    python3 bin/ssot/scene-trigger.py --activate <scene_id> --to pilot
    python3 bin/ssot/scene-trigger.py --trigger <signal_id>  # 手动触发
    python3 bin/ssot/scene-trigger.py --dry-run       # 模拟运行
"""

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCENE_DIR = REPO / "docs" / "scene-cards"
JOURNEY_DIR = REPO / "docs" / "journey-specs"
SIGNAL_SOURCES = REPO / ".omo" / "_truth" / "registry" / "signal-sources.yaml"


def load_scenes() -> list[dict]:
    """加载所有 scene-card (支持多文档 YAML)."""
    import yaml
    scenes = []
    if not SCENE_DIR.exists():
        return scenes
    for f in sorted(SCENE_DIR.glob("*.yaml")):
        try:
            text = f.read_text()
            # 解析 frontmatter
            fm = {}
            if text.startswith("---"):
                end = text.find("---", 3)
                if end > 0:
                    fm = yaml.safe_load(text[3:end]) or {}
            # 解析全文获取 scene_id / journey_id 等
            try:
                docs = list(yaml.safe_load_all(text))
                for doc in docs:
                    if isinstance(doc, dict):
                        for k in ("scene_id", "journey_id", "trigger", "activation"):
                            if k in doc and k not in fm:
                                fm[k] = doc[k]
            except Exception:
                pass
            if isinstance(fm, dict):
                fm["_file"] = str(f.relative_to(REPO))
                scenes.append(fm)
        except Exception:
            continue
    return scenes


def load_journeys() -> list[dict]:
    """加载所有 journey-spec."""
    import yaml
    journeys = []
    if not JOURNEY_DIR.exists():
        return journeys
    for f in sorted(JOURNEY_DIR.glob("*.yaml")):
        try:
            data = yaml.safe_load(f.read_text()) or {}
            if isinstance(data, dict) and "journey_id" in data:
                journeys.append(data)
        except Exception:
            continue
    return journeys


def find_journey(journey_id: str, journeys: list[dict]) -> dict | None:
    """查找旅程 (支持模糊匹配)."""
    # 精确匹配
    for j in journeys:
        if j.get("journey_id") == journey_id:
            return j
    # 模糊匹配
    for j in journeys:
        if journey_id in j.get("journey_id", "") or j.get("journey_id", "") in journey_id:
            return j
    return None


def activate_scene(scene_id: str, target: str) -> dict:
    """激活场景状态."""
    scenes = load_scenes()
    for s in scenes:
        if s.get("scene_id") == scene_id:
            old_status = s.get("status", "unknown")
            # 状态机: shadow → pilot → active
            transitions = {"shadow": "pilot", "pilot": "active"}
            if old_status == target:
                return {"ok": True, "msg": f"already {target}", "scene": scene_id}
            if transitions.get(old_status) == target:
                return {
                    "ok": True,
                    "msg": f"{old_status} → {target}",
                    "scene": scene_id,
                    "action": "manual_activation_required",
                    "edit_file": s.get("_file"),
                }
            return {"ok": False, "msg": f"cannot transition {old_status} → {target}", "scene": scene_id}
    return {"ok": False, "msg": f"scene not found: {scene_id}"}


def trigger_scene(signal_id: str, dry_run: bool = False) -> dict:
    """根据信号触发场景."""
    import yaml
    if not SIGNAL_SOURCES.exists():
        return {"ok": False, "msg": "signal-sources.yaml not found"}

    # 加载信号源
    try:
        data = yaml.safe_load(SIGNAL_SOURCES.read_text()) or {}
    except Exception as e:
        return {"ok": False, "msg": f"parse error: {e}"}

    sources = data.get("sources", [])
    matching = [s for s in sources if s.get("id") == signal_id]
    if not matching:
        return {"ok": False, "msg": f"signal not found: {signal_id}"}

    source = matching[0]
    scene_binding = source.get("scene_binding", "")

    # 查找匹配的 scene-card
    scenes = load_scenes()
    matching_scenes = [s for s in scenes if s.get("scene_id") == scene_binding or scene_binding in str(s)]
    if not matching_scenes:
        return {"ok": False, "msg": f"no scene bound to signal: {scene_binding}"}

    scene = matching_scenes[0]
    status = scene.get("status", "unknown")

    if status == "shadow":
        return {"ok": False, "msg": f"scene {scene_binding} is shadow, activate first", "scene": scene}

    # 查找 journey
    journey_id = scene.get("journey_id", "")
    journeys = load_journeys()
    journey = find_journey(journey_id, journeys)

    result = {
        "ok": True,
        "signal": signal_id,
        "scene": scene_binding,
        "journey": journey_id,
        "journey_found": journey is not None,
    }

    if dry_run:
        result["dry_run"] = True
        return result

    # 执行旅程
    if journey:
        try:
            sys.path.insert(0, str(REPO / "projects" / "ecos" / "src"))
            from ecos.l1.runtime.journey_runner import JourneyRunner
            runner = JourneyRunner()
            exec_result = runner.execute_journey(journey_id)
            result["execution"] = exec_result
        except Exception as e:
            result["execution_error"] = str(e)

    return result


def main():
    parser = argparse.ArgumentParser(description="Scene Trigger")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--activate")
    parser.add_argument("--to", default="pilot")
    parser.add_argument("--trigger")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if args.list:
        scenes = load_scenes()
        active = [s for s in scenes if s.get("status") in ("pilot", "active")]
        result = {
            "total": len(scenes),
            "active": [{"id": s.get("scene_id"), "status": s.get("status")} for s in active],
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    if args.status:
        scenes = load_scenes()
        result = {s.get("scene_id", "?"): s.get("status", "?") for s in scenes}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    if args.activate:
        result = activate_scene(args.activate, args.to)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    if args.trigger:
        result = trigger_scene(args.trigger, dry_run=args.dry_run)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return


if __name__ == "__main__":
    sys.exit(main())
