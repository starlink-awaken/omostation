#!/usr/bin/env python3
"""Record admission evidence for internal pipeline scene cards.

Joins an existing internal pipeline Scene Card with the internal-scene-preflight
checks and persists the trial evidence to
``.omo/_knowledge/workflow-mesh/internal-scene-trials.jsonl``.

The JSONL file satisfies scene-card-lifecycle Check4 (trial_recorded) so that
the lifecycle gate can transition from blocked to ready.

Usage::

    python3 bin/ssot/internal-scene-trial.py --list
    python3 bin/ssot/internal-scene-trial.py --scene engineering-delivery
    python3 bin/ssot/internal-scene-trial.py --scene engineering-delivery --record
    python3 bin/ssot/internal-scene-trial.py --scene engineering-delivery --record --json
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCHEMA = "internal-scene-trial/v1"
TRIAL_LOG_REL = ".omo/_knowledge/workflow-mesh/internal-scene-trials.jsonl"
SCENE_CARD_DIR = "docs/scene-cards"


class PreflightFailedError(Exception):
    """Raised when preflight checks fail and --record cannot proceed."""


# ---------------------------------------------------------------------------
# Module loading (same pattern as external-scene-trial.py)
# ---------------------------------------------------------------------------


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _load_yaml_scene_card(path: Path) -> dict[str, Any]:
    """Load a scene card YAML file (supports multi-document)."""
    import yaml

    with open(path, encoding="utf-8") as f:
        docs = list(yaml.safe_load_all(f))
    body = docs[-1] if len(docs) > 1 else docs[0]
    if not isinstance(body, dict):
        raise ValueError(f"scene card YAML must produce an object: {path}")
    return body


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------


def list_internal_scenes(*, root: Path) -> list[dict[str, Any]]:
    """List internal_pipeline scene cards and their trial status."""
    scene_dir = root / SCENE_CARD_DIR
    if not scene_dir.is_dir():
        return []

    trial_log = root / TRIAL_LOG_REL
    recorded_ids: set[str] = set()
    if trial_log.exists():
        for line in trial_log.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                recorded_ids.add(entry.get("scene_id", ""))
            except json.JSONDecodeError:
                continue

    results: list[dict[str, Any]] = []
    for card_path in sorted(scene_dir.glob("*.yaml")):
        try:
            card = _load_yaml_scene_card(card_path)
        except Exception:
            continue
        scene_type = card.get("scene_type", "")
        if scene_type != "internal_pipeline":
            continue
        scene_id = card.get("scene_id", card_path.stem)
        results.append({
            "scene_id": scene_id,
            "scene_type": scene_type,
            "lifecycle": card.get("lifecycle", "?"),
            "trial_status": "recorded" if scene_id in recorded_ids else "not_recorded",
            "card_path": str(card_path.relative_to(root)),
        })

    return results


def run_preflight(*, root: Path, scene_card: dict[str, Any]) -> dict[str, Any]:
    """Run internal-scene-preflight on a scene card (read-only)."""
    preflight_mod = _load_module(
        root / "bin/ssot/internal-scene-preflight.py",
        "internal_preflight_for_trial",
    )
    # Preflight only accepts scene-card/v1 or None; strip v2 schema
    card = dict(scene_card)
    if card.get("schema") not in (None, "scene-card/v1"):
        card.pop("schema", None)
    return preflight_mod.build_preflight(card, root=root)


def record_trial(
    *,
    root: Path,
    scene_card: dict[str, Any],
    evidence_ref: str,
    operator: str = "internal-scene-trial",
    trial_log_path: Path | None = None,
) -> dict[str, Any]:
    """Run preflight; if pass, append trial evidence to JSONL.

    Raises PreflightFailedError if preflight does not pass.

    Args:
        trial_log_path: Override for the JSONL output path (for testing).
            Defaults to ``root / TRIAL_LOG_REL``.
    """
    preflight = run_preflight(root=root, scene_card=scene_card)

    if preflight["status"] != "ready_for_admission_preview":
        raise PreflightFailedError(
            f"preflight blocked: {preflight['missing_fields']}"
        )

    scene_id = scene_card.get("scene_id", "unknown")
    entry = {
        "schema": SCHEMA,
        "scene_id": scene_id,
        "recorded_at": datetime.now(UTC).isoformat(),
        "evidence_ref": evidence_ref,
        "verdict": "pass",
        "operator": operator,
        "preflight_status": preflight["status"],
    }

    trial_log = trial_log_path or (root / TRIAL_LOG_REL)
    trial_log.parent.mkdir(parents=True, exist_ok=True)
    with open(trial_log, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")

    return entry


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--scene", help="scene_id to run preflight on")
    parser.add_argument("--record", action="store_true", help="persist trial evidence to JSONL (requires --scene)")
    parser.add_argument("--json", action="store_true", dest="json_output", help="output as JSON")
    parser.add_argument("--list", action="store_true", dest="list_scenes", help="list internal pipeline scene cards")
    parser.add_argument("--evidence-ref", default="evidence://internal-scene-trial/admission", help="evidence reference")
    parser.add_argument("--operator", default="internal-scene-trial", help="operator name")
    args = parser.parse_args(argv)

    # --list
    if args.list_scenes:
        results = list_internal_scenes(root=args.root)
        if args.json_output:
            print(json.dumps(results, ensure_ascii=False, indent=2, sort_keys=True))
        else:
            if not results:
                print("No internal_pipeline scene cards found.")
            for entry in results:
                status_marker = "✓" if entry["trial_status"] == "recorded" else "✗"
                print(f"  [{status_marker}] {entry['scene_id']} ({entry['lifecycle']}) — {entry['trial_status']}")
        return 0

    # --scene (with or without --record)
    if args.scene:
        # Find the scene card
        scene_dir = args.root / SCENE_CARD_DIR
        card_path = None
        for p in sorted(scene_dir.glob("*.yaml")):
            try:
                card = _load_yaml_scene_card(p)
                if card.get("scene_id") == args.scene:
                    card_path = p
                    break
            except Exception:
                continue

        if card_path is None:
            print(f"internal-scene-trial: scene card not found: {args.scene}", file=sys.stderr)
            return 1

        scene_card = _load_yaml_scene_card(card_path)

        if args.record:
            try:
                entry = record_trial(
                    root=args.root,
                    scene_card=scene_card,
                    evidence_ref=args.evidence_ref,
                    operator=args.operator,
                )
                if args.json_output:
                    print(json.dumps(entry, ensure_ascii=False, indent=2, sort_keys=True))
                else:
                    print(f"Trial recorded for {args.scene}: {entry['recorded_at']}")
                    print(f"  evidence_ref: {entry['evidence_ref']}")
                    print(f"  verdict: {entry['verdict']}")
                return 0
            except PreflightFailedError as exc:
                print(f"internal-scene-trial: {exc}", file=sys.stderr)
                return 1
        else:
            # Just run preflight
            try:
                result = run_preflight(root=args.root, scene_card=scene_card)
            except Exception as exc:
                print(f"internal-scene-trial: preflight error: {exc}", file=sys.stderr)
                return 2

            if args.json_output:
                print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
            else:
                status = result["status"]
                print(f"Scene: {args.scene}")
                print(f"  Status: {status}")
                if result.get("missing_fields"):
                    print(f"  Missing: {result['missing_fields']}")
                else:
                    print("  All checks passed.")
            return 0 if result["status"] == "ready_for_admission_preview" else 1

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
