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


def trigger_scene(scene_id: str) -> dict:
    card_path = REPO / "docs" / "scene-cards" / f"{scene_id}.yaml"
    if not card_path.exists():
        return {"ok": False, "error": "not found"}
    content = card_path.read_text(encoding="utf-8")
    if "lifecycle: assisted" not in content and "lifecycle: active" not in content:
        return {"ok": False, "error": "not active"}
    r = subprocess.run(
        ["python3", str(REPO / "bin/gac/scene-journey-connector.py"), "--create", scene_id],
        capture_output=True, text=True, check=False, cwd=str(REPO),
    )
    return {"ok": r.returncode == 0, "scene": scene_id}


def auto_trigger_all() -> dict:
    cards_dir = REPO / "docs" / "scene-cards"
    results = []
    for card in sorted(cards_dir.glob("*.yaml")):
        content = card.read_text(encoding="utf-8")
        if "lifecycle: assisted" in content or "lifecycle: active" in content:
            results.append(trigger_scene(card.stem))
    return {"ok": True, "total": len(results), "triggered": sum(1 for r in results if r.get("ok"))}


def main() -> int:
    parser = argparse.ArgumentParser(description="Signal → Scene 连接器")
    parser.add_argument("--scene", help="Trigger specific scene")
    parser.add_argument("--auto-trigger-all", action="store_true")
    args = parser.parse_args()

    if args.scene:
        print(json.dumps(trigger_scene(args.scene), indent=2, ensure_ascii=False))
        return 0
    if args.auto_trigger_all:
        print(json.dumps(auto_trigger_all(), indent=2, ensure_ascii=False))
        return 0
    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
