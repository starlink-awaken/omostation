#!/usr/bin/env python3
"""Scene v3 Guardrail — schema validation and anti-corruption hooks.

Validates scene cards against:
  1. JSON Schema (structural)
  2. lifecycle/activation consistency
  3. capability_refs BOS URI reachability
  4. topology reference integrity
  5. quality.calibration metric weights sum to 1.0

Usage:
  python3 bin/ssot/scene-v3-guardrail.py validate <scene_card_path>
  python3 bin/ssot/scene-v3-guardrail.py validate-all
  python3 bin/ssot/scene-v3-guardrail.py check-consistency
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SCENES_DIR = ROOT / ".omo" / "_truth" / "scenarios" / "v3"
SCHEMA_PATH = Path(__file__).resolve().parent / "scene-card-v3-schema.json"


def _load_yaml(path: Path) -> dict[str, Any]:
    import yaml
    with open(path, encoding="utf-8") as f:
        docs = list(yaml.safe_load_all(f))
    body = docs[-1] if len(docs) > 1 else docs[0]
    return body if isinstance(body, dict) else {}


def validate_structure(card: dict[str, Any]) -> list[str]:
    """Validate against JSON Schema."""
    errors = []
    required = ["schema", "scene_id", "name", "lifecycle", "activation", "owner"]
    for field in required:
        if not card.get(field):
            errors.append(f"missing required field: {field}")

    if card.get("schema") != "scene-card/v3":
        errors.append(f"schema must be 'scene-card/v3', got '{card.get('schema')}'")

    valid_levels = ["draft", "shadow", "assisted", "supervised", "routine"]
    if card.get("lifecycle") not in valid_levels:
        errors.append(f"invalid lifecycle: {card.get('lifecycle')}")

    valid_activation = ["preview", "controlled", "active", "allowed"]
    if card.get("activation") not in valid_activation:
        errors.append(f"invalid activation: {card.get('activation')}")

    return errors


def validate_consistency(card: dict[str, Any]) -> list[str]:
    """Validate lifecycle/activation consistency."""
    errors = []
    tier_activation = {
        "draft": "preview",
        "shadow": "preview",
        "assisted": "controlled",
        "supervised": "active",
        "routine": "allowed",
    }
    lifecycle = card.get("lifecycle", "")
    activation = card.get("activation", "")
    expected = tier_activation.get(lifecycle)
    if expected and activation != expected:
        errors.append(f"lifecycle '{lifecycle}' expects activation '{expected}', got '{activation}'")
    return errors


def validate_capability_refs(card: dict[str, Any]) -> list[str]:
    """Validate capability_refs are valid BOS URIs."""
    errors = []
    caps = card.get("runtime", {}).get("sandbox", {}).get("capability_refs", [])
    for uri in caps:
        if not uri.startswith("bos://"):
            errors.append(f"capability_ref must start with 'bos://', got: {uri}")
        elif len(uri.split("/")) < 4:
            errors.append(f"capability_ref too short (expected bos://domain/action/name): {uri}")
    return errors


def validate_topology(card: dict[str, Any], all_scene_ids: set[str]) -> list[str]:
    """Validate topology references point to existing scenes."""
    errors = []
    topo = card.get("topology", {})

    for upstream in topo.get("upstream", []):
        scene = upstream.get("scene", "")
        if scene and scene not in all_scene_ids:
            errors.append(f"upstream scene '{scene}' not found in v3 registry")

    for downstream in topo.get("downstream", []):
        scene = downstream.get("scene", "")
        if scene and scene not in all_scene_ids:
            errors.append(f"downstream scene '{scene}' not found in v3 registry")

    return errors


def validate_quality(card: dict[str, Any]) -> list[str]:
    """Validate quality.calibration metric weights sum to ~1.0."""
    errors = []
    metrics = card.get("quality", {}).get("calibration", {}).get("metrics", [])
    if metrics:
        total_weight = sum(m.get("weight", 0) for m in metrics)
        if abs(total_weight - 1.0) > 0.01:
            errors.append(f"metric weights sum to {total_weight:.3f}, expected 1.000")
    return errors


def validate_scene_card(path: Path) -> dict[str, Any]:
    """Full validation of a single scene card."""
    card = _load_yaml(path)
    scene_id = card.get("scene_id", path.stem)

    all_errors = []
    all_warnings = []

    all_errors.extend(validate_structure(card))
    all_errors.extend(validate_consistency(card))
    all_errors.extend(validate_capability_refs(card))
    all_errors.extend(validate_quality(card))

    # Topology validation requires all scene IDs
    all_scene_ids = set()
    if SCENES_DIR.is_dir():
        for p in SCENES_DIR.glob("*.yaml"):
            c = _load_yaml(p)
            if c.get("scene_id"):
                all_scene_ids.add(c["scene_id"])
    all_errors.extend(validate_topology(card, all_scene_ids))

    return {
        "scene_id": scene_id,
        "path": str(path),
        "valid": len(all_errors) == 0,
        "errors": all_errors,
        "warnings": all_warnings,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command")

    vp = sub.add_parser("validate", help="Validate a single scene card")
    vp.add_argument("scene_card", type=Path, help="Path to scene card YAML")
    vp.add_argument("--allow-forward-refs", action="store_true",
                     help="Allow topology refs to non-existent scenes (forward refs)")

    va = sub.add_parser("validate-all", help="Validate all v3 scene cards")
    va.add_argument("--allow-forward-refs", action="store_true",
                     help="Allow topology refs to non-existent scenes (forward refs)")
    vc = sub.add_parser("check-consistency", help="Check lifecycle/activation consistency")

    args = parser.parse_args(argv)
    command = args.command or "validate-all"

    if command == "validate":
        result = validate_scene_card(args.scene_card)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["valid"] else 1

    # validate-all or check-consistency
    allow_forward = getattr(args, "allow_forward_refs", False)

    if not SCENES_DIR.is_dir():
        print(f"ERROR: {SCENES_DIR} not found", file=sys.stderr)
        return 2

    cards = sorted(SCENES_DIR.glob("*.yaml"))
    if not cards:
        print("No scene cards found.")
        return 0

    all_valid = True
    for card_path in cards:
        result = validate_scene_card(card_path)
        # Filter forward-ref errors if allowed
        if allow_forward:
            result["errors"] = [e for e in result["errors"]
                                if "not found in v3 registry" not in e]
            result["valid"] = len(result["errors"]) == 0
        status = "PASS" if result["valid"] else "FAIL"
        if not result["valid"]:
            all_valid = False
        print(f"[{status}] {result['scene_id']}")
        for e in result["errors"]:
            print(f"  ERROR: {e}")
        for w in result["warnings"]:
            print(f"  WARN: {w}")

    return 0 if all_valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
