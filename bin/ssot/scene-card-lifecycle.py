#!/usr/bin/env python3
"""Scene card lifecycle management — check readiness and activate internal pipeline scenes.

Provides explicit lifecycle transitions with precondition checks.
Never auto-activates — every transition requires a human operator command.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _load_yaml_scene_card(path: Path) -> dict[str, Any]:
    import yaml

    with open(path, encoding="utf-8") as f:
        docs = list(yaml.safe_load_all(f))
    body = docs[-1] if len(docs) > 1 else docs[0]
    if not isinstance(body, dict):
        raise ValueError(f"scene card YAML must produce an object: {path}")
    return body


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


VALID_LIFECYCLE_TIERS = ("draft", "shadow", "assisted", "supervised", "routine")

LEGACY_LIFECYCLE_MAP = {
    "proposal_only": "draft",
    "active": "routine",
    "forbidden": "draft",
}


def validate_scene_card_v2(card: dict[str, Any]) -> dict[str, Any]:
    """Validate scene card against v2 schema: 5-tier lifecycle + bet/falsifier."""
    errors: list[str] = []
    warnings: list[str] = []

    lifecycle = card.get("lifecycle", "")
    if lifecycle in LEGACY_LIFECYCLE_MAP:
        warnings.append(
            f"lifecycle '{lifecycle}' is legacy; map to '{LEGACY_LIFECYCLE_MAP[lifecycle]}'"
        )
    elif lifecycle and lifecycle not in VALID_LIFECYCLE_TIERS:
        errors.append(
            f"lifecycle '{lifecycle}' not in {VALID_LIFECYCLE_TIERS}"
        )

    if not card.get("bet"):
        errors.append("required field 'bet' is missing")
    if not card.get("falsifier"):
        errors.append("required field 'falsifier' is missing")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "lifecycle": lifecycle,
        "tier": lifecycle if lifecycle in VALID_LIFECYCLE_TIERS else LEGACY_LIFECYCLE_MAP.get(lifecycle, "unknown"),
    }


def check_readiness(root: Path, scene_card_path: Path) -> dict[str, Any]:
    """Check if a scene card is ready for activation (read-only, no side effects)."""
    card = _load_yaml_scene_card(scene_card_path)
    scene_type = card.get("scene_type", "external_resource")
    checks: dict[str, Any] = {
        "scene_id": card.get("scene_id", "?"),
        "scene_type": scene_type,
        "lifecycle": card.get("lifecycle", "?"),
        "activation": card.get("activation", "?"),
        "approval_state": card.get("approval_state", "?"),
        "activation_blockers": card.get("activation_blockers", []),
        "preconditions": {},
        "ready": False,
    }

    # Check 1: blockers must be empty
    blockers = card.get("activation_blockers", [])
    checks["preconditions"]["blockers_empty"] = len(blockers) == 0

    # Check 2: approval_state must be confirmed
    checks["preconditions"]["approval_confirmed"] = card.get("approval_state") == "confirmed"

    # Check 3: run track-specific preflight
    if scene_type == "internal_pipeline":
        preflight_mod = _load_module(
            root / "bin/ssot/internal-scene-preflight.py", "internal_preflight_for_lifecycle"
        )
        preflight = preflight_mod.build_preflight(card, root=root)
        checks["preconditions"]["preflight_pass"] = preflight["status"] == "ready_for_admission_preview"
        checks["preflight_detail"] = {
            "status": preflight["status"],
            "missing_fields": preflight["missing_fields"],
        }
    else:
        # External track: delegate to external-scene-trial for preflight
        checks["preconditions"]["preflight_pass"] = True  # external track has its own tools

    # Check 4: trial evidence must exist
    if scene_type == "internal_pipeline":
        trial_log = root / ".omo" / "_knowledge" / "workflow-mesh" / "internal-scene-trials.jsonl"
    else:
        trial_log = root / ".omo" / "_knowledge" / "workflow-mesh" / "external-scene-trials.jsonl"
    checks["preconditions"]["trial_recorded"] = trial_log.exists()

    # Aggregate
    checks["ready"] = all(checks["preconditions"].values())

    return checks


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--scene-card", type=Path)
    parser.add_argument("--all", action="store_true", help="validate all scene cards in docs/scene-cards/")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("check", help="check readiness (read-only)")
    sub.add_parser("validate", help="validate v2 schema (5-tier lifecycle + bet/falsifier)")
    activate_parser = sub.add_parser("activate", help="activate scene card (requires explicit command)")
    activate_parser.add_argument("--actor", required=True, help="operator name")
    args = parser.parse_args(argv)

    command = args.command or "check"

    if command == "validate":
        scene_dir = args.root / "docs" / "scene-cards"
        cards = []
        if args.all and scene_dir.is_dir():
            cards = sorted(scene_dir.glob("*.yaml"))
        elif args.scene_card:
            cards = [args.scene_card]
        else:
            print("ERROR: --scene-card or --all required for validate", file=sys.stderr)
            return 2

        all_valid = True
        for card_path in cards:
            card = _load_yaml_scene_card(card_path)
            result = validate_scene_card_v2(card)
            scene_id = card.get("scene_id", card_path.stem)
            status = "PASS" if result["valid"] else "FAIL"
            if not result["valid"]:
                all_valid = False
            print(f"[{status}] {scene_id}: tier={result['tier']}")
            for e in result["errors"]:
                print(f"  ERROR: {e}")
            for w in result["warnings"]:
                print(f"  WARN: {w}")
        return 0 if all_valid else 1

    if command == "check":
        result = check_readiness(args.root, args.scene_card)
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return 0 if result["ready"] else 1

    if command == "activate":
        readiness = check_readiness(args.root, args.scene_card)
        if not readiness["ready"]:
            print("ERROR: scene card not ready for activation:", file=sys.stderr)
            print(json.dumps(readiness["preconditions"], indent=2), file=sys.stderr)
            return 1

        # Read, update, write scene card
        import yaml

        with open(args.scene_card, encoding="utf-8") as f:
            raw = f.read()
        docs = list(yaml.safe_load_all(raw))
        body_idx = len(docs) - 1 if len(docs) > 1 else 0
        body = docs[body_idx]

        body["lifecycle"] = "active"
        body["activation"] = "allowed"
        body["approval_state"] = "approved"
        body["activation_blockers"] = []
        if "notes" not in body:
            body["notes"] = []
        body["notes"].append(
            f"Activated {datetime.now(UTC).isoformat()} by {args.actor} "
            f"(preconditions verified: {readiness['preconditions']})"
        )

        docs[body_idx] = body
        with open(args.scene_card, "w", encoding="utf-8") as f:
            yaml.dump_all(docs, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

        print(f"Activated: {body['scene_id']} by {args.actor}")
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
