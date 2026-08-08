#!/usr/bin/env python3
"""Scene Outcome Recorder — 结果面人类裁决记录 (四面一脊 ④).

Records human adjudication after a scene/journey reaches terminal state.
Supports accepted/rejected/revised outcomes with revision notes.
Feeds back into scene-reflection for feedforward learning.

Usage:
  python3 bin/ssot/scene-outcome-recorder.py record --scene-card <path> --run-id <id> --adjudication accepted
  python3 bin/ssot/scene-outcome-recorder.py list --scene-id <id> --limit 10
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

OUTCOME_SCHEMA = "scene-outcome/v1"
ROOT = Path(__file__).resolve().parents[2]
OUTCOME_LOG = ROOT / ".omo" / "_knowledge" / "workflow-mesh" / "scene-outcomes.jsonl"
VALID_ADJUDICATIONS = {"accepted", "rejected", "revised"}


def _load_scene_card(path: Path) -> dict[str, Any]:
    import yaml

    docs = list(yaml.safe_load_all(path.read_text(encoding="utf-8")))
    body = docs[-1] if docs else {}
    if not isinstance(body, dict):
        raise ValueError(f"scene card must be an object: {path}")
    return body


def record_outcome(
    scene_card_path: Path,
    run_id: str,
    adjudication: str,
    *,
    actor: str = "operator",
    notes: str = "",
    revision_diff: str = "",
) -> dict[str, Any]:
    """Record one human adjudication outcome."""
    if adjudication not in VALID_ADJUDICATIONS:
        raise ValueError(f"adjudication must be one of {VALID_ADJUDICATIONS}")

    card = _load_scene_card(scene_card_path)
    scene_id = card.get("scene_id", "unknown")
    ts = datetime.now(UTC).isoformat()

    entry = {
        "ts": ts,
        "schema": OUTCOME_SCHEMA,
        "scene_id": scene_id,
        "run_id": run_id,
        "adjudication": adjudication,
        "actor": actor,
        "notes": notes[:500],
        "revision_diff": revision_diff[:500],
        "digest": f"sha256:{hashlib.sha256(f'{scene_id}:{run_id}:{adjudication}:{ts}'.encode()).hexdigest()[:16]}",
    }

    OUTCOME_LOG.parent.mkdir(parents=True, exist_ok=True)

    import fcntl

    with open(OUTCOME_LOG, "a", encoding="utf-8") as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        try:
            f.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")
            f.flush()
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    entry["status"] = "recorded"
    return entry


def list_outcomes(scene_id: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
    """List recent outcomes, optionally filtered by scene_id."""
    if not OUTCOME_LOG.exists():
        return []
    entries: list[dict[str, Any]] = []
    for line in OUTCOME_LOG.read_text(encoding="utf-8").strip().split("\n"):
        if not line:
            continue
        try:
            entry = json.loads(line)
            if scene_id is None or entry.get("scene_id") == scene_id:
                entries.append(entry)
        except json.JSONDecodeError:
            continue
    return entries[-limit:]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)

    sub = parser.add_subparsers(dest="command")

    rec_parser = sub.add_parser("record", help="record one outcome")
    rec_parser.add_argument("--scene-card", type=Path, required=True)
    rec_parser.add_argument("--run-id", required=True)
    rec_parser.add_argument("--adjudication", required=True, choices=sorted(VALID_ADJUDICATIONS))
    rec_parser.add_argument("--actor", default="operator")
    rec_parser.add_argument("--notes", default="")
    rec_parser.add_argument("--revision-diff", default="")

    list_parser = sub.add_parser("list", help="list recent outcomes")
    list_parser.add_argument("--scene-id", default=None)
    list_parser.add_argument("--limit", type=int, default=20)

    args = parser.parse_args(argv)
    command = args.command or "list"

    if command == "record":
        result = record_outcome(
            args.scene_card, args.run_id, args.adjudication,
            actor=args.actor, notes=args.notes, revision_diff=args.revision_diff,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return 0

    if command == "list":
        entries = list_outcomes(scene_id=args.scene_id, limit=args.limit)
        if not entries:
            print("No outcomes recorded yet.")
            return 0
        print(f"Recent outcomes ({len(entries)} entries):")
        for e in entries:
            print(f"  {e['ts'][:19]}  {e.get('scene_id','?'):25s}  {e['adjudication']:10s}  by={e['actor']}")
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
