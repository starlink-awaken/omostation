#!/usr/bin/env python3
"""Scene Card → Journey 接线器.

当场景卡升级到 assisted 时，自动创建对应的 Journey.
衔接 scene-card-mini-shadow 与 journey-runner.

Usage:
    python3 bin/gac/scene-journey-connector.py --list
    python3 bin/gac/scene-journey-connector.py --create <scene_id>
    python3 bin/gac/scene-journey-connector.py --auto-create
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCENES_DIR = REPO / "docs" / "scene-cards"
JOURNEY_RUNNER = REPO / "bin" / "ssot" / "journey-runner.py"
STATE_FILE = REPO / ".omo" / "state" / "scene-journey-map.json"


def _state_file(root: Path) -> Path:
    return root / ".omo" / "state" / "scene-journey-map.json"


def _load_state(root: Path) -> dict:
    state_file = _state_file(root)
    if state_file.exists():
        try:
            return json.loads(state_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {"mappings": [], "version": "1.0"}
    return {"mappings": [], "version": "1.0"}


def _save_state(root: Path, data: dict) -> None:
    state_file = _state_file(root)
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _load_yaml_simple(path: Path) -> dict:
    try:
        import yaml

        with open(path, encoding="utf-8") as f:
            docs = list(yaml.safe_load_all(f))
        body = docs[-1] if len(docs) > 1 else docs[0]
        return body if isinstance(body, dict) else {}
    except Exception:
        return {}


def list_eligible_cards(root: Path = REPO) -> list[dict]:
    """List scene cards eligible for journey creation."""
    scenes_dir = root / "docs" / "scene-cards"
    state = _load_state(root)
    eligible = []
    for p in sorted(scenes_dir.glob("*.yaml")):
        body = _load_yaml_simple(p)
        lifecycle = body.get("lifecycle", "")
        scene_id = body.get("scene_id", p.stem)
        journey_id = body.get("journey_id", "")

        if lifecycle == "assisted" and journey_id:
            # Check if journey already created
            existing = [m for m in state.get("mappings", []) if m.get("scene_id") == scene_id]
            if not existing:
                eligible.append({
                    "scene_id": scene_id,
                    "journey_id": journey_id,
                    "path": str(p),
                })
    return eligible


def create_journey(scene_id: str, root: Path = REPO) -> dict:
    """Create a journey for an assisted scene card."""
    # Find the scene card
    card_path = root / "docs" / "scene-cards" / f"{scene_id}.yaml"
    if not card_path.exists():
        return {"ok": False, "error": f"scene card not found: {scene_id}"}

    body = _load_yaml_simple(card_path)
    journey_id = body.get("journey_id", "")
    if not journey_id:
        return {"ok": False, "error": f"no journey_id in scene card: {scene_id}"}

    # Check if journey spec exists
    journey_spec = root / "docs" / "journey-specs" / f"{journey_id}.yaml"
    if not journey_spec.exists():
        return {"ok": False, "error": f"journey spec not found: {journey_id}"}

    # Record the mapping
    state = _load_state(root)
    mapping = {
        "scene_id": scene_id,
        "journey_id": journey_id,
        "created_at": datetime.now(UTC).isoformat(),
        "status": "created",
    }
    state.setdefault("mappings", []).append(mapping)
    _save_state(root, state)

    return {
        "ok": True,
        "scene_id": scene_id,
        "journey_id": journey_id,
        "message": f"Journey {journey_id} created for scene {scene_id}",
    }


def auto_create(root: Path = REPO) -> list[dict]:
    """Auto-create journeys for all eligible scene cards."""
    eligible = list_eligible_cards(root)
    results = []
    for card in eligible:
        result = create_journey(card["scene_id"], root)
        results.append(result)
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Scene Card → Journey 接线器")
    parser.add_argument("--root", type=Path, default=REPO, help="repository root")
    parser.add_argument("--list", action="store_true", help="List eligible scene cards")
    parser.add_argument("--create", help="Create journey for specific scene_id")
    parser.add_argument("--auto-create", action="store_true", help="Auto-create all eligible journeys")
    args = parser.parse_args()

    if args.list:
        eligible = list_eligible_cards(args.root)
        if not eligible:
            print("没有可创建 Journey 的场景卡")
            return 0
        print(f"可创建 Journey 的场景卡 ({len(eligible)}):")
        for card in eligible:
            print(f"  {card['scene_id']} → {card['journey_id']}")
        return 0

    if args.create:
        result = create_journey(args.create, args.root)
        if result.get("ok"):
            print(f"✓ {result['message']}")
            return 0
        else:
            print(f"✗ {result.get('error', 'unknown error')}")
            return 1

    if args.auto_create:
        results = auto_create(args.root)
        if not results:
            print("没有可创建 Journey 的场景卡")
            return 0
        print(f"自动创建 Journey ({len(results)}):")
        for r in results:
            if r.get("ok"):
                print(f"  ✓ {r['message']}")
            else:
                print(f"  ✗ {r.get('error', 'unknown')}")
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
