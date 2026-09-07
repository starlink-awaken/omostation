#!/usr/bin/env python3
"""Scene BOS Registration — register scene cards as BOS services.

Scans .omo/_truth/scenarios/v3/ and generates BOS service entries:
  bos://scene/{scene_id}/execute  → execute scene journey
  bos://scene/{scene_id}/status    → get scene lifecycle status
  bos://scene/{scene_id}/calibrate → compute calibration score

Usage:
  python3 bin/ssot/scene-bos-register.py generate
  python3 bin/ssot/scene-bos-register.py register [--dry-run]
  python3 bin/ssot/scene-bos-register.py list
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SCENES_DIR = ROOT / ".omo" / "_truth" / "scenarios" / "v3"
BOS_SERVICES = ROOT / "projects" / "agora" / "etc" / "bos-services.yaml"


def _load_scene(scene_id: str) -> dict[str, Any] | None:
    import yaml
    for p in SCENES_DIR.glob("*.yaml"):
        try:
            with open(p, encoding="utf-8") as f:
                docs = list(yaml.safe_load_all(f))
            body = docs[-1] if len(docs) > 1 else docs[0]
            if isinstance(body, dict) and body.get("scene_id") == scene_id:
                return body
        except Exception:
            continue
    return None


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


def generate_entries(scenes: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """Generate BOS service entries for scenes."""
    if scenes is None:
        scenes = _load_all_scenes()

    entries = []
    for scene in scenes:
        scene_id = scene.get("scene_id", "")
        if not scene_id:
            continue

        lifecycle = scene.get("lifecycle", "draft")
        status = "active" if lifecycle in ("assisted", "supervised", "routine") else "inactive"

        entries.append({
            "uri": f"bos://scene/{scene_id}/execute",
            "domain": "scene",
            "package": "scene-engine",
            "action": "execute",
            "transport": "internal",
            "module_path": "bin.ssot.journey_engine",
            "func_name": "execute_journey",
            "status": status,
            "description": f"Execute scene {scene_id} ({lifecycle})",
        })

        entries.append({
            "uri": f"bos://scene/{scene_id}/status",
            "domain": "scene",
            "package": "scene-engine",
            "action": "status",
            "transport": "internal",
            "module_path": "bin.ssot.scene-card-lifecycle",
            "func_name": "check_readiness",
            "status": "active",
            "description": f"Get scene {scene_id} lifecycle status",
        })

        entries.append({
            "uri": f"bos://scene/{scene_id}/calibrate",
            "domain": "scene",
            "package": "scene-engine",
            "action": "calibrate",
            "transport": "internal",
            "module_path": "bin.ssot.calibration_engine",
            "func_name": "compute_calibration",
            "status": "active",
            "description": f"Compute calibration for {scene_id}",
        })

    return entries


def register(dry_run: bool = False) -> tuple[int, int]:
    """Register scene BOS entries into bos-services.yaml."""
    import yaml

    if not BOS_SERVICES.exists():
        print(f"WARNING: {BOS_SERVICES} not found (agora submodule not initialized)", file=sys.stderr)
        print("Generating entries only...", file=sys.stderr)
        entries = generate_entries()
        print(json.dumps({"would_register": len(entries), "services": BOS_SERVICES.exists()}, indent=2))
        return len(entries), 0

    with open(BOS_SERVICES, encoding="utf-8") as f:
        content = f.read()

    data = yaml.safe_load(content)
    existing = data.get("services", []) if isinstance(data, dict) else []
    existing_uris = {e.get("uri", "") for e in existing if isinstance(e, dict)}

    new_entries = generate_entries()
    added = 0
    for entry in new_entries:
        if entry["uri"] not in existing_uris:
            existing.append(entry)
            existing_uris.add(entry["uri"])
            added += 1

    if dry_run:
        print(f"[DRY RUN] Would add {added} scene BOS entries")
        return added, len(existing)

    data["services"] = existing
    with open(BOS_SERVICES, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    return added, len(existing)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("generate", help="Generate BOS entries (stdout)")
    rp = sub.add_parser("register", help="Register in bos-services.yaml")
    rp.add_argument("--dry-run", action="store_true")
    sub.add_parser("list", help="List scene BOS URIs")

    args = parser.parse_args(argv)
    command = args.command or "list"

    if command == "generate":
        entries = generate_entries()
        print(json.dumps(entries, ensure_ascii=False, indent=2))
        return 0

    if command == "register":
        added, total = register(dry_run=getattr(args, "dry_run", False))
        print(f"Scene BOS entries: {added} added, {total} total")
        return 0

    # list
    entries = generate_entries()
    for e in entries:
        print(f"  {e['uri']}  [{e['status']}]")
    print(f"\nTotal: {len(entries)} entries ({len(entries)//3} scenes × 3 ops)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
