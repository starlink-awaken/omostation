#!/usr/bin/env python3
"""kems-scene-bridge.py — KEMS 变更检测 → 场景触发桥接.

用法:
    python3 bin/gac/kems-scene-bridge.py --check
    python3 bin/gac/kems-scene-bridge.py --trigger <scope>
    python3 bin/gac/kems-scene-bridge.py --status
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
KEMS_CHECK_SCRIPT = REPO / "projects" / "runtime" / "src" / "runtime" / "documents_plane" / "kems.py"

SCOPE_TO_SCENE = {
    "inbox": "documents-owner-job",
    "knowledge": "documents-learning-control",
    "entities": "documents-consumer-audit",
    "control": "documents-controller-preflight",
    "buffer_inbox": "documents-workspace-watch",
}

SCENE_JOURNEY_ENTRY = {
    "documents-owner-job": "discover",
    "documents-learning-control": "discover",
    "documents-consumer-audit": "scan",
    "documents-controller-preflight": "check_dependencies",
    "documents-workspace-watch": "detect",
}


def run_kems_check() -> dict:
    """Run KEMS change detection."""
    try:
        result = subprocess.run(
            [sys.executable, str(KEMS_CHECK_SCRIPT), "--json"],
            capture_output=True, text=True, cwd=str(REPO), timeout=30,
        )
        if result.returncode == 0:
            return json.loads(result.stdout)
    except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError):
        pass
    return {"ok": False, "changed_scopes": [], "error": "kems check unavailable"}


def resolve_scene(scope: str) -> str | None:
    """Resolve KEMS scope to scene ID."""
    return SCOPE_TO_SCENE.get(scope)


def trigger_scene(scene_id: str, context: dict | None = None) -> dict:
    """Trigger a scene journey."""
    return {
        "scene_id": scene_id,
        "triggered_at": datetime.now(UTC).isoformat(),
        "entry_state": SCENE_JOURNEY_ENTRY.get(scene_id, "detected"),
        "context": context or {},
        "ok": True,
    }


def check_and_trigger() -> dict:
    """Check KEMS changes and trigger scenes."""
    kems_result = run_kems_check()
    changed_scopes = kems_result.get("changed_scopes", [])
    triggered = []
    for scope in changed_scopes:
        scene_id = resolve_scene(scope)
        if scene_id:
            triggered.append(trigger_scene(scene_id, {"scope": scope}))
    return {
        "timestamp": datetime.now(UTC).isoformat(),
        "kems_result": kems_result,
        "triggered_scenes": triggered,
        "ok": True,
    }


def trigger_scope(scope: str) -> int:
    """Manually trigger a scene by scope."""
    scene_id = resolve_scene(scope)
    if not scene_id:
        print(f"未知 scope: {scope}", file=sys.stderr)
        return 1
    result = trigger_scene(scene_id, {"manual": True, "scope": scope})
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def show_status() -> int:
    """Show bridge status."""
    print("KEMS → Scene 桥接状态")
    print("=" * 50)
    print("\nScope 映射:")
    for scope, scene_id in sorted(SCOPE_TO_SCENE.items()):
        entry = SCENE_JOURNEY_ENTRY.get(scene_id, "detected")
        print(f"  {scope:20s} → {scene_id} (entry: {entry})")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="KEMS → Scene 运行时桥接")
    parser.add_argument("--check", action="store_true", help="检查 KEMS 变更并触发")
    parser.add_argument("--trigger", metavar="SCOPE", help="手动触发场景")
    parser.add_argument("--status", action="store_true", help="显示状态")
    args = parser.parse_args()

    if args.status:
        return show_status()
    if args.trigger:
        return trigger_scope(args.trigger)

    result = check_and_trigger()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
