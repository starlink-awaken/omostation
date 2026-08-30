#!/usr/bin/env python3
"""Signal → Scene Card 连接器."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
STATE_FILE = REPO / ".omo" / "state" / "signal-scene-state.json"


def _load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {"triggers": [], "version": "1.0"}


def _save_state(data: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def trigger_scene(scene_id: str) -> dict:
    """Trigger a scene card and create a journey."""
    card_path = REPO / "docs" / "scene-cards" / f"{scene_id}.yaml"
    if not card_path.exists():
        return {"ok": False, "scene": scene_id, "error": "scene card not found"}

    content = card_path.read_text(encoding="utf-8")
    if "lifecycle: assisted" not in content and "lifecycle: active" not in content:
        return {"ok": False, "scene": scene_id, "error": "scene card not active"}

    # Create journey
    journey_result = subprocess.run(
        ["python3", str(REPO / "bin/gac/scene-journey-connector.py"), "--create", scene_id],
        capture_output=True, text=True, check=False, cwd=str(REPO),
    )

    trigger_record = {
        "scene": scene_id,
        "triggered_at": datetime.now(timezone.utc).isoformat(),
        "journey_created": journey_result.returncode == 0,
    }

    state = _load_state()
    state.setdefault("triggers", []).append(trigger_record)
    _save_state(state)

    return trigger_record


def auto_trigger_all() -> dict:
    """Auto-trigger all eligible scene cards."""
    cards_dir = REPO / "docs" / "scene-cards"
    if not cards_dir.exists():
        return {"ok": False, "error": "scene-cards directory not found"}

    results = []
    for card_path in sorted(cards_dir.glob("*.yaml")):
        content = card_path.read_text(encoding="utf-8")
        if "lifecycle: assisted" in content or "lifecycle: active" in content:
            scene_id = card_path.stem
            result = trigger_scene(scene_id)
            results.append(result)

    return {
        "ok": True,
        "total": len(results),
        "triggered": sum(1 for r in results if r.get("journey_created")),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Signal → Scene Card 连接器")
    parser.add_argument("--scene", help="Trigger specific scene")
    parser.add_argument("--auto-trigger-all", action="store_true", help="Trigger all eligible scenes")
    args = parser.parse_args()

    if args.scene:
        result = trigger_scene(args.scene)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if result.get("ok") else 1

    if args.auto_trigger_all:
        result = auto_trigger_all()
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
