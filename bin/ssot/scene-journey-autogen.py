#!/usr/bin/env python3
"""Scene Journey Auto-Generator — generate journey specs from scene cards.

For scenes without a journey spec, generates one based on:
  - scene_type (inbound/outbound/cycle)
  - scene_class (business/governance/infra)
  - domain
  - description/goal

Usage:
  python3 bin/ssot/scene-journey-autogen.py scan
  python3 bin/ssot/scene-journey-autogen.py generate [--dry-run]
  python3 bin/ssot/scene-journey-autogen.py validate
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SCENES_DIR = ROOT / ".omo" / "_truth" / "scenarios" / "v3"
JOURNEYS_DIR = ROOT / ".omo" / "_truth" / "journeys" / "v3"

# ── Journey templates by scene_type ─────────────────────────────────

TEMPLATES = {
    "inbound": {
        "states": [
            {"name": "detected", "type": "initial", "description": "信号到达"},
            {"name": "classified", "type": "task", "action": "llm_classify", "timeout": "30s", "description": "LLM 分类"},
            {"name": "processing", "type": "task", "action": "process", "timeout": "120s", "description": "核心处理"},
            {"name": "review_gate", "type": "human_gate", "requires_human": True, "approval_timeout": "86400s", "description": "人机介入门控"},
            {"name": "recorded", "type": "task", "action": "record_result", "description": "记录结果"},
            {"name": "knowledge_capture", "type": "task", "action": "emit_event", "event": "scene.completed", "description": "知识沉淀"},
            {"name": "completed", "type": "final"},
            {"name": "escalated", "type": "final"},
        ],
        "transitions": [
            {"from": "detected", "to": "classified"},
            {"from": "classified", "to": "processing"},
            {"from": "processing", "to": "review_gate"},
            {"from": "review_gate", "to": "recorded", "condition": "confidence >= 0.7"},
            {"from": "review_gate", "to": "escalated", "condition": "confidence < 0.5"},
            {"from": "recorded", "to": "knowledge_capture"},
            {"from": "knowledge_capture", "to": "completed"},
        ],
    },
    "outbound": {
        "states": [
            {"name": "triggered", "type": "initial", "description": "触发发起"},
            {"name": "prepared", "type": "task", "action": "prepare_content", "timeout": "60s", "description": "准备内容"},
            {"name": "review_gate", "type": "human_gate", "requires_human": True, "approval_timeout": "86400s", "description": "发送前审批"},
            {"name": "dispatched", "type": "task", "action": "dispatch", "timeout": "60s", "description": "发送/派发"},
            {"name": "confirmed", "type": "task", "action": "confirm_delivery", "description": "确认送达"},
            {"name": "completed", "type": "final"},
        ],
        "transitions": [
            {"from": "triggered", "to": "prepared"},
            {"from": "prepared", "to": "review_gate"},
            {"from": "review_gate", "to": "dispatched", "condition": "confidence >= 0.7"},
            {"from": "dispatched", "to": "confirmed"},
            {"from": "confirmed", "to": "completed"},
        ],
    },
    "cycle": {
        "states": [
            {"name": "triggered", "type": "initial", "description": "定时触发"},
            {"name": "collecting", "type": "task", "action": "collect_data", "timeout": "300s", "description": "采集数据"},
            {"name": "processing", "type": "task", "action": "process_data", "timeout": "120s", "description": "处理数据"},
            {"name": "generating", "type": "task", "action": "generate_output", "timeout": "60s", "description": "生成输出"},
            {"name": "completed", "type": "final"},
        ],
        "transitions": [
            {"from": "triggered", "to": "collecting"},
            {"from": "collecting", "to": "processing"},
            {"from": "processing", "to": "generating"},
            {"from": "generating", "to": "completed"},
        ],
    },
}

# Governance scenes use a simpler template
GOVERNANCE_TEMPLATE = {
    "states": [
        {"name": "detected", "type": "initial"},
        {"name": "preflight", "type": "task", "action": "preflight_check", "timeout": "30s"},
        {"name": "executing", "type": "task", "action": "execute", "timeout": "120s"},
        {"name": "verifying", "type": "task", "action": "verify_result", "timeout": "30s"},
        {"name": "completed", "type": "final"},
        {"name": "escalated", "type": "final"},
    ],
    "transitions": [
        {"from": "detected", "to": "preflight"},
        {"from": "preflight", "to": "executing"},
        {"from": "executing", "to": "verifying"},
        {"from": "verifying", "to": "completed"},
    ],
}


def _get_template(scene: dict[str, Any]) -> dict[str, Any]:
    """Select the appropriate journey template for a scene."""
    scene_class = scene.get("scene_class", "business")
    if scene_class == "governance":
        return GOVERNANCE_TEMPLATE
    scene_type = scene.get("scene_type", "inbound")
    return TEMPLATES.get(scene_type, TEMPLATES["inbound"])


def _load_all_scenes() -> list[dict[str, Any]]:
    import yaml
    scenes = []
    if SCENES_DIR.is_dir():
        for p in sorted(SCENES_DIR.glob("*.yaml")):
            try:
                with open(p, encoding="utf-8") as f:
                    docs = list(yaml.safe_load_all(f))
                body = docs[-1] if len(docs) > 1 else docs[0]
                if isinstance(body, dict):
                    scenes.append(body)
            except Exception:
                continue
    return scenes


def _get_existing_journeys() -> set[str]:
    existing = set()
    if JOURNEYS_DIR.is_dir():
        for f in JOURNEYS_DIR.glob("*.yaml"):
            existing.add(f.stem)
    return existing


def scan() -> list[dict[str, Any]]:
    """Find scenes missing journey specs."""
    scenes = _load_all_scenes()
    existing = _get_existing_journeys()
    missing = []

    for scene in scenes:
        scene_id = scene.get("scene_id", "")
        journey_ref = scene.get("runtime", {}).get("journey_ref", "")
        if not journey_ref:
            journey_ref = f"journey-{scene_id}"
        if journey_ref in existing:
            continue
        missing.append({
            "scene_id": scene_id,
            "journey_ref": journey_ref,
            "scene_type": scene.get("scene_type", "inbound"),
            "scene_class": scene.get("scene_class", "business"),
            "name": scene.get("name", ""),
        })

    return missing


def generate_spec(scene: dict[str, Any]) -> dict[str, Any]:
    """Generate a journey spec from a scene card."""
    template = _get_template(scene)
    scene_id = scene.get("scene_id", "")
    journey_ref = scene.get("runtime", {}).get("journey_ref", f"journey-{scene_id}")
    name = scene.get("name", scene_id)
    description = scene.get("description", "")

    spec = {
        "schema": "journey-spec/v3",
        "journey_id": journey_ref,
        "name": f"{name} 旅程",
        "description": description or f"Auto-generated journey for {name}",
        "initial_state": template["states"][0]["name"],
        "states": template["states"],
        "transitions": template["transitions"],
    }

    # Add compensation if the scene has compensation config
    comp = scene.get("runtime", {}).get("compensation", {})
    if comp:
        spec["compensation"] = {
            "recorded": {"type": "emit_event", "payload": {"event_type": "scene.compensation.rollback"}},
        }

    return spec


def generate(dry_run: bool = False) -> tuple[int, int]:
    """Generate missing journey specs."""
    import yaml
    missing = scan()
    generated = 0

    for item in missing:
        scenes = _load_all_scenes()
        scene = next((s for s in scenes if s.get("scene_id") == item["scene_id"]), None)
        if not scene:
            continue

        spec = generate_spec(scene)
        out_path = JOURNEYS_DIR / f"{item['journey_ref']}.yaml"

        if dry_run:
            print(f"  [DRY RUN] {item['journey_ref']} ({item['scene_type']}/{item['scene_class']})")
            generated += 1
            continue

        JOURNEYS_DIR.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            yaml.dump(spec, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
        generated += 1
        print(f"  Generated: {item['journey_ref']}")

    return generated, len(missing)


def validate_all() -> tuple[int, int]:
    """Validate all journey specs."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "journey_engine", str(ROOT / "bin" / "ssot" / "journey-engine.py"))
    je = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(je)

    valid = invalid = 0
    if JOURNEYS_DIR.is_dir():
        for f in sorted(JOURNEYS_DIR.glob("*.yaml")):
            journey_id = f.stem
            try:
                journey_spec = je._load_yaml(f)
                backedges = je._detect_backedges(journey_spec)
                states = len(journey_spec.get("states", []))
                transitions = len(journey_spec.get("transitions", []))
                status = "PASS" if len(backedges) == 0 and states > 0 else "FAIL"
                if status == "PASS":
                    valid += 1
                else:
                    invalid += 1
                    print(f"  [{status}] {journey_id}: backedges={len(backedges)}, states={states}")
            except Exception as e:
                invalid += 1
                print(f"  [FAIL] {journey_id}: {e}")

    return valid, invalid


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("scan", help="Scan for missing journey specs")
    gp = sub.add_parser("generate", help="Generate missing journey specs")
    gp.add_argument("--dry-run", action="store_true")
    sub.add_parser("validate", help="Validate all journey specs")
    sub.add_parser("report", help="Report journey coverage")

    args = parser.parse_args(argv)
    command = args.command or "scan"

    if command == "scan":
        missing = scan()
        print(f"Missing journey specs: {len(missing)}")
        for m in missing[:15]:
            print(f"  {m['scene_id']:<35} → {m['journey_ref']} ({m['scene_type']}/{m['scene_class']})")
        if len(missing) > 15:
            print(f"  ... and {len(missing) - 15} more")

    elif command == "generate":
        generated, total = generate(dry_run=getattr(args, "dry_run", False))
        print(f"\nGenerated: {generated}/{total}")

    elif command == "validate":
        valid, invalid = validate_all()
        print(f"Journey specs: {valid} valid, {invalid} invalid")
        return 0 if invalid == 0 else 1

    elif command == "report":
        missing = scan()
        existing = _get_existing_journeys()
        total_scenes = len(_load_all_scenes())
        print(f"Total scenes: {total_scenes}")
        print(f"Existing journey specs: {len(existing)}")
        print(f"Missing journey specs: {len(missing)}")
        print(f"Coverage: {len(existing)}/{total_scenes} ({len(existing)*100//total_scenes}%)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
