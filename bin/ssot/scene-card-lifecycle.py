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
        warnings.append(f"lifecycle '{lifecycle}' is legacy; map to '{LEGACY_LIFECYCLE_MAP[lifecycle]}'")
    elif lifecycle and lifecycle not in VALID_LIFECYCLE_TIERS:
        errors.append(f"lifecycle '{lifecycle}' not in {VALID_LIFECYCLE_TIERS}")

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


VALID_TRANSITIONS = {
    ("draft", "shadow"),
    ("shadow", "assisted"),
    ("assisted", "supervised"),
    ("supervised", "routine"),
    ("shadow", "draft"),
    ("assisted", "shadow"),
    ("supervised", "assisted"),
    ("routine", "supervised"),
}

LEGACY_TO_TIER = {
    "proposal_only": "draft",
    "active": "routine",
    "forbidden": "draft",
}

TIER_ACTIVATION = {
    "draft": "forbidden",
    "shadow": "preview",
    "assisted": "controlled",
    "supervised": "monitored",
    "routine": "allowed",
}


def _resolve_tier(lifecycle: str) -> str:
    if lifecycle in VALID_LIFECYCLE_TIERS:
        return lifecycle
    return LEGACY_TO_TIER.get(lifecycle, lifecycle)


def transition_scene_card(
    scene_card_path: Path,
    target_tier: str,
    actor: str,
    root: Path | None = None,
) -> dict[str, Any]:
    """Transition a scene card to a new lifecycle tier."""
    import yaml

    if target_tier not in VALID_LIFECYCLE_TIERS:
        return {"ok": False, "error": f"invalid tier: {target_tier}"}

    with open(scene_card_path, encoding="utf-8") as f:
        docs = list(yaml.safe_load_all(f))
    body_idx = len(docs) - 1 if len(docs) > 1 else 0
    body = docs[body_idx]

    current_tier = _resolve_tier(body.get("lifecycle", "draft"))
    if (current_tier, target_tier) not in VALID_TRANSITIONS:
        return {
            "ok": False,
            "error": f"transition {current_tier}→{target_tier} not allowed",
            "valid_transitions": [f"{a}→{b}" for a, b in VALID_TRANSITIONS if a == current_tier],
        }

    if target_tier in ("assisted", "supervised", "routine"):
        if root is None:
            root = Path(__file__).resolve().parents[2]
        readiness = check_readiness(root, scene_card_path)
        if not readiness["ready"]:
            return {
                "ok": False,
                "error": f"not ready for {target_tier}",
                "preconditions": readiness["preconditions"],
            }

    body["lifecycle"] = target_tier
    body["activation"] = TIER_ACTIVATION[target_tier]
    if target_tier == "shadow":
        body["activation_blockers"] = []
        body["approval_state"] = body.get("approval_state", "confirmed")

    if "notes" not in body:
        body["notes"] = []
    body["notes"].append(f"Transitioned {current_tier}→{target_tier} at {datetime.now(UTC).isoformat()} by {actor}")

    docs[body_idx] = body
    with open(scene_card_path, "w", encoding="utf-8") as f:
        yaml.dump_all(docs, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    return {
        "ok": True,
        "scene_id": body.get("scene_id"),
        "from": current_tier,
        "to": target_tier,
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
            root / "bin/ssot/internal-scene-preflight.py",
            "internal_preflight_for_lifecycle",
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

    # Check 4: trial evidence must exist (BET-Y2Q1-T7-02: 按 scene 精确匹配,
    # 不再是文件级存在性 — 三类试验日志任一含本 scene 的条目即算数。
    # shadow-scene-trials.jsonl 由 journey-runner 完成 run 后落盘, mode 字段
    # 诚实区分 dry_run/live; internal/external 条目带 scene_id 字段)
    mesh = root / ".omo" / "_knowledge" / "workflow-mesh"
    trial_logs = [
        mesh / "internal-scene-trials.jsonl",
        mesh / "external-scene-trials.jsonl",
        mesh / "shadow-scene-trials.jsonl",
    ]
    scene_id_target = str(card.get("scene_id", ""))
    trial_recorded = False
    for log_path in trial_logs:
        if not log_path.exists():
            continue
        for line in log_path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            if scene_id_target and (
                entry.get("scene_id") == scene_id_target
                or scene_id_target in (entry.get("scene_ids") or [])
            ):
                trial_recorded = True
                break
        if trial_recorded:
            break
    checks["preconditions"]["trial_recorded"] = trial_recorded

    # Aggregate
    checks["ready"] = all(checks["preconditions"].values())

    return checks


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    sub = parser.add_subparsers(dest="command")
    check_parser = sub.add_parser("check", help="check readiness (read-only)")
    check_parser.add_argument("--scene-card", type=Path, required=True)
    validate_parser = sub.add_parser("validate", help="validate v2 schema (5-tier lifecycle + bet/falsifier)")
    validate_parser.add_argument("--scene-card", type=Path)
    validate_parser.add_argument(
        "--all",
        action="store_true",
        help="validate all scene cards in docs/scene-cards/",
    )
    activate_parser = sub.add_parser("activate", help="activate scene card (requires explicit command)")
    activate_parser.add_argument("--scene-card", type=Path, required=True)
    activate_parser.add_argument("--actor", required=True, help="operator name")
    transition_parser = sub.add_parser("transition", help="transition scene card to a new lifecycle tier")
    transition_parser.add_argument("--scene-card", type=Path, required=True)
    transition_parser.add_argument("--tier", required=True, choices=VALID_LIFECYCLE_TIERS, help="target tier")
    transition_parser.add_argument("--actor", required=True, help="operator name")
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
        try:
            result = check_readiness(args.root, args.scene_card)
        except Exception as exc:
            # Keep the honest gate machine-readable even when a card is
            # malformed or violates a preflight contract.  A traceback is
            # useful for debugging but is not stable evidence for a gate.
            print(
                json.dumps(
                    {
                        "error": str(exc),
                        "error_type": type(exc).__name__,
                        "ready": False,
                        "scene_card": str(args.scene_card),
                    },
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
            )
            return 2
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

    if command == "transition":
        result = transition_scene_card(args.scene_card, args.tier, args.actor, root=args.root)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["ok"] else 1

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
