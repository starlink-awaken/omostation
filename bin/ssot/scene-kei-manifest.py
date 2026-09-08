#!/usr/bin/env python3
"""Scene KEI Manifest — generate sandbox manifests from scene cards.

Generates KEI (Kernel Execution Isolation) manifests from scene card
permission_scope and capability declarations.

Usage:
  python3 bin/ssot/scene-kei-manifest.py generate <scene_id>
  python3 bin/ssot/scene-kei-manifest.py generate-all
  python3 bin/ssot/scene-kei-manifest.py validate <scene_id> --action <action> --target <path>
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SCENES_DIR = ROOT / ".omo" / "_truth" / "scenarios" / "v3"
MANIFESTS_DIR = ROOT / ".omo" / "_truth" / "kei-manifests"

# Permission scope → KEI permissions mapping
SCOPE_MAP = {
    "workflow-read": {"fs_read": [".omo/"], "fs_write": [], "network": []},
    "evidence-write": {"fs_read": [], "fs_write": [".omo/_knowledge/", ".omo/_delivery/"], "network": []},
    "knowledge-write": {"fs_read": [], "fs_write": ["data/", ".omo/_knowledge/"], "network": []},
    "config-write": {"fs_read": [], "fs_write": ["config/"], "network": []},
    "state-write": {"fs_read": [], "fs_write": [".omo/state/"], "network": []},
}

# BOS domain → network access
DOMAIN_NETWORK = {
    "memory": ["localhost:8766", "localhost:5432"],  # KOS REST, gbrain Postgres
    "capability": ["localhost:9290", "localhost:4000"],  # AetherForge
    "analysis": ["localhost:8766"],
    "governance": ["localhost:7431"],  # Cockpit SSE
    "scene": [],  # Internal calls, no network
    "agent-cell": [],
}


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


def generate_manifest(scene_id: str) -> dict[str, Any] | None:
    """Generate KEI manifest for a scene."""
    scene = _load_scene(scene_id)
    if not scene:
        return None

    permissions = {"fs_read": [], "fs_write": [], "network": [], "shell_exec": False}
    scopes = scene.get("runtime", {}).get("sandbox", {}).get("permissions", [])
    if not scopes:
        scopes = scene.get("permission_scope", [])
    capabilities = scene.get("runtime", {}).get("sandbox", {}).get("capabilities", [])

    # Map permission scopes
    for scope in scopes:
        mapping = SCOPE_MAP.get(scope, {})
        permissions["fs_read"].extend(mapping.get("fs_read", []))
        permissions["fs_write"].extend(mapping.get("fs_write", []))

    # Map capability_refs to network access
    for cap in capabilities:
        if cap.startswith("iris:") or cap.startswith("connector:"):
            permissions["network"].append("iris-connector")
            continue
        if cap.startswith("llm:"):
            permissions["network"].append("localhost:9290")
            continue
        parts = cap.replace("bos://", "").split("/")
        domain = parts[0] if parts else ""
        hosts = DOMAIN_NETWORK.get(domain, [])
        permissions["network"].extend(hosts)

    # Deduplicate
    permissions["fs_read"] = sorted(set(permissions["fs_read"]))
    permissions["fs_write"] = sorted(set(permissions["fs_write"]))
    permissions["network"] = sorted(set(permissions["network"]))

    manifest = {
        "schema": "kei-manifest/v1",
        "scene_id": scene_id,
        "name": scene.get("name", scene_id),
        "lifecycle": scene.get("lifecycle", "draft"),
        "permissions": permissions,
        "generated_at": __import__("datetime").datetime.now(__import__("datetime").UTC).isoformat(),
    }

    return manifest


def validate_action(scene_id: str, action: str, target: str) -> dict[str, Any]:
    """Validate a scene action against its KEI manifest."""
    manifest = generate_manifest(scene_id)
    if not manifest:
        return {"allowed": False, "reason": f"Scene not found: {scene_id}"}

    perms = manifest["permissions"]

    if action == "read":
        allowed = any(target.startswith(p) or p in ("", "/") for p in perms["fs_read"])
        return {"allowed": allowed, "reason": f"fs_read check for {target}"}

    if action == "write":
        allowed = any(target.startswith(p) for p in perms["fs_write"])
        return {"allowed": allowed, "reason": f"fs_write check for {target}"}

    if action == "network":
        host = target.split(":")[0] if ":" in target else target
        allowed = any(host in n for n in perms["network"])
        return {"allowed": allowed, "reason": f"network check for {target}"}

    if action == "shell":
        return {"allowed": perms.get("shell_exec", False), "reason": "shell_exec check"}

    return {"allowed": False, "reason": f"Unknown action: {action}"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command")

    gp = sub.add_parser("generate", help="Generate KEI manifest for a scene")
    gp.add_argument("scene_id")
    ga = sub.add_parser("generate-all", help="Generate manifests for all scenes")
    vp = sub.add_parser("validate", help="Validate a scene action")
    vp.add_argument("scene_id")
    vp.add_argument("--action", required=True, choices=["read", "write", "network", "shell"])
    vp.add_argument("--target", required=True)

    args = parser.parse_args(argv)
    command = args.command or "generate-all"

    if command == "generate":
        manifest = generate_manifest(args.scene_id)
        if not manifest:
            print(f"ERROR: scene not found: {args.scene_id}", file=sys.stderr)
            return 2
        print(json.dumps(manifest, ensure_ascii=False, indent=2))
        return 0

    if command == "generate-all":
        import yaml
        MANIFESTS_DIR.mkdir(parents=True, exist_ok=True)
        generated = 0
        if SCENES_DIR.is_dir():
            for p in sorted(SCENES_DIR.glob("*.yaml")):
                try:
                    with open(p, encoding="utf-8") as f:
                        docs = list(yaml.safe_load_all(f))
                    body = docs[-1] if len(docs) > 1 else docs[0]
                    if not isinstance(body, dict):
                        continue
                    scene_id = body.get("scene_id", p.stem)
                    manifest = generate_manifest(scene_id)
                    if manifest:
                        out = MANIFESTS_DIR / f"{scene_id}.json"
                        with open(out, "w", encoding="utf-8") as f:
                            json.dump(manifest, f, ensure_ascii=False, indent=2)
                        generated += 1
                except Exception as e:
                    print(f"  WARN: {p.name}: {e}", file=sys.stderr)
        print(f"Generated {generated} KEI manifests to {MANIFESTS_DIR.relative_to(ROOT)}")
        return 0

    if command == "validate":
        result = validate_action(args.scene_id, args.action, args.target)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["allowed"] else 1

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
