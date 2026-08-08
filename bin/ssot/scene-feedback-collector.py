#!/usr/bin/env python3
"""Collect outcome-feedback for active scene cards.

Reads a scene card's outcome_metric, accepts a metric value from the operator,
and appends a feedback entry to the scene feedback log. Supports listing
recent feedback for review.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

FEEDBACK_SCHEMA = "outcome-feedback/v1"


def _load_scene_card(path: Path) -> dict[str, Any]:
    import yaml

    docs = list(yaml.safe_load_all(path.read_text(encoding="utf-8")))
    body = docs[-1] if docs else {}
    if not isinstance(body, dict):
        raise ValueError(f"scene card must be an object: {path}")
    return body


def _feedback_log(root: Path) -> Path:
    return root / ".omo" / "_knowledge" / "workflow-mesh" / "scene-feedback.jsonl"


def record_feedback(
    root: Path,
    scene_card_path: Path,
    metric_value: float,
    *,
    actor: str = "operator",
    notes: str = "",
) -> dict[str, Any]:
    """Record one feedback entry for a scene's outcome metric."""
    card = _load_scene_card(scene_card_path)
    scene_id = card.get("scene_id", "unknown")
    metric = card.get("outcome_metric", "unknown")

    entry = {
        "ts": datetime.now(UTC).isoformat(),
        "schema": FEEDBACK_SCHEMA,
        "scene_id": scene_id,
        "metric": metric,
        "value": metric_value,
        "actor": actor,
        "notes": notes,
        "digest": f"sha256:{hashlib.sha256(f'{scene_id}:{metric}:{metric_value}:{datetime.now(UTC).isoformat()}'.encode()).hexdigest()[:16]}",
    }

    log_path = _feedback_log(root)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    import fcntl

    with open(log_path, "a", encoding="utf-8") as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        try:
            f.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")
            f.flush()
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    return {"status": "recorded", "scene_id": scene_id, "metric": metric, "value": metric_value}


def list_feedback(root: Path, scene_id: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
    """List recent feedback entries, optionally filtered by scene_id."""
    log_path = _feedback_log(root)
    if not log_path.exists():
        return []

    entries: list[dict[str, Any]] = []
    for line in log_path.read_text(encoding="utf-8").strip().split("\n"):
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
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])

    sub = parser.add_subparsers(dest="command")

    record_parser = sub.add_parser("record", help="record one feedback entry")
    record_parser.add_argument("--scene-card", type=Path, required=True)
    record_parser.add_argument("--metric-value", type=float, required=True)
    record_parser.add_argument("--actor", default="operator")
    record_parser.add_argument("--notes", default="")

    list_parser = sub.add_parser("list", help="list recent feedback")
    list_parser.add_argument("--scene-id", default=None)
    list_parser.add_argument("--limit", type=int, default=20)

    args = parser.parse_args(argv)
    command = args.command or "list"

    if command == "record":
        result = record_feedback(
            args.root, args.scene_card, args.metric_value,
            actor=args.actor, notes=args.notes,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return 0

    if command == "list":
        entries = list_feedback(args.root, scene_id=args.scene_id, limit=args.limit)
        if not entries:
            print("No feedback entries found.")
            return 0
        print(f"Recent feedback ({len(entries)} entries):")
        for e in entries:
            print(f"  {e['ts'][:19]}  {e['scene_id']:30s}  {e['metric']:40s}  value={e['value']}  by={e['actor']}")
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
