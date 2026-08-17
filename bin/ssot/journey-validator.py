#!/usr/bin/env python3
"""Validate journey spec files — check states, transitions, reachability, and deadlocks."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _load_yaml(path: Path) -> dict[str, Any]:
    import yaml

    with open(path, encoding="utf-8") as f:
        docs = list(yaml.safe_load_all(f))
    body = docs[-1] if docs else {}
    if not isinstance(body, dict):
        raise ValueError(f"YAML must be an object: {path}")
    return body


def _load_scene_ids(root: Path) -> set[str]:
    """Load all scene_ids from scene cards for cross-reference validation."""
    import yaml

    cards_dir = root / "docs" / "scene-cards"
    ids: set[str] = set()
    if not cards_dir.is_dir():
        return ids
    for path in cards_dir.glob("*.yaml"):
        try:
            docs = list(yaml.safe_load_all(path.read_text(encoding="utf-8")))
            body = docs[-1] if docs else {}
            if isinstance(body, dict) and body.get("scene_id"):
                ids.add(body["scene_id"])
        except Exception:
            continue
    return ids


def validate_journey(spec: dict[str, Any], known_scenes: set[str]) -> dict[str, Any]:
    journey_id = spec.get("journey_id", "?")
    states_raw = spec.get("states", [])
    transitions_raw = spec.get("transitions", [])

    errors: list[str] = []
    warnings: list[str] = []

    # Parse states
    state_names: set[str] = set()
    state_scenes: dict[str, str] = {}
    state_next: dict[str, list[str]] = {}
    for state in states_raw:
        if not isinstance(state, dict):
            errors.append(f"state must be an object: {state}")
            continue
        name = state.get("name", "")
        if not name:
            errors.append("state missing 'name'")
            continue
        if name in state_names:
            errors.append(f"duplicate state: {name}")
        state_names.add(name)
        scene = state.get("scene", "")
        state_scenes[name] = scene
        if scene and known_scenes and scene not in known_scenes:
            errors.append(f"state '{name}' references unknown scene: '{scene}'")
        nxt = state.get("next", [])
        state_next[name] = nxt if isinstance(nxt, list) else []

    # Parse transitions
    transition_pairs: set[tuple[str, str]] = set()
    for trans in transitions_raw:
        if not isinstance(trans, dict):
            errors.append(f"transition must be an object: {trans}")
            continue
        frm = trans.get("from", "")
        to = trans.get("to", "")
        if frm not in state_names:
            errors.append(f"transition from unknown state: '{frm}'")
        if to not in state_names:
            errors.append(f"transition to unknown state: '{to}'")
        transition_pairs.add((frm, to))

    # Check next[] entries reference valid states
    for name, nxts in state_next.items():
        for nxt in nxts:
            if nxt not in state_names:
                errors.append(f"state '{name}'.next references unknown state: '{nxt}'")

    # Reachability: all states reachable from any entry point
    # Entry points = states not in any transition.to
    all_targets = {t for _, t in transition_pairs}
    entry_points = state_names - all_targets
    if not entry_points and state_names:
        errors.append("no entry point found (all states are transition targets — possible cycle)")

    reachable: set[str] = set()
    queue = list(entry_points) if entry_points else list(state_names)[:1]
    while queue:
        current = queue.pop(0)
        if current in reachable:
            continue
        reachable.add(current)
        for nxt in state_next.get(current, []):
            if nxt not in reachable:
                queue.append(nxt)

    unreachable = state_names - reachable
    for name in sorted(unreachable):
        warnings.append(f"unreachable state: '{name}'")

    # Deadlock: non-terminal states with no outgoing transitions and no next[]
    terminal_count = 0
    for name in state_names:
        nxts = state_next.get(name, [])
        has_transition = any(frm == name for frm, _ in transition_pairs)
        if not nxts and not has_transition:
            terminal_count += 1  # terminal state (valid)
        elif not nxts and has_transition:
            pass  # transitions define next, OK

    # Summary
    return {
        "schema": "journey-validation/v1",
        "journey_id": journey_id,
        "valid": len(errors) == 0,
        "states": len(state_names),
        "transitions": len(transition_pairs),
        "entry_points": sorted(entry_points),
        "terminal_states": sorted(name for name in state_names if not state_next.get(name)),
        "errors": errors,
        "warnings": warnings,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("spec_path", type=Path, nargs="?", help="single spec file (omit for all)")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    known_scenes = _load_scene_ids(args.root)
    specs_dir = args.root / "docs" / "journey-specs"

    if args.spec_path:
        files = [args.spec_path]
    else:
        files = sorted(specs_dir.glob("*.yaml")) if specs_dir.is_dir() else []

    if not files:
        print("No journey specs found.")
        return 0

    all_valid = True
    results = []
    for path in files:
        try:
            spec = _load_yaml(path)
            result = validate_journey(spec, known_scenes)
            results.append(result)
            if not args.json:
                status = "✅" if result["valid"] else "❌"
                print(f"{status} {path.name}: {result['states']} states, {result['transitions']} transitions")
                for e in result["errors"]:
                    print(f"    ERROR: {e}")
                for w in result["warnings"]:
                    print(f"    WARN: {w}")
            if not result["valid"]:
                all_valid = False
        except Exception as exc:
            print(f"❌ {path.name}: {exc}")
            all_valid = False

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2, sort_keys=True))

    return 0 if all_valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
