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

from _shared import ROOT, append_jsonl, load_yaml, read_jsonl, utc_now

OUTCOME_SCHEMA = "scene-outcome/v1"
OUTCOME_LOG = ROOT / ".omo" / "_knowledge" / "workflow-mesh" / "scene-outcomes.jsonl"
VALID_ADJUDICATIONS = {"accepted", "rejected", "revised"}


def _load_scene_card(path: Path) -> dict[str, Any]:
    body = load_yaml(path)
    if not body:
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
    ts = utc_now()

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

    append_jsonl(OUTCOME_LOG, entry)

    # T-B2: outcome → MOS decision_outcome bridge (控制论反馈闭环).
    # 结果写入 MOS 因果模型, Trust Policy 读取后可校准能力评估.
    mos_outcome_id = _write_mos_decision_outcome(entry)
    entry["mos_outcome_id"] = mos_outcome_id

    entry["status"] = "recorded"
    return entry


def _write_mos_decision_outcome(entry: dict[str, Any]) -> str | None:
    """Write outcome to MOS decision_outcome (复用 omo_belief.MOSBeliefManager)."""
    try:
        import sys

        omo_src = str(ROOT / "projects" / "omo" / "src")
        if omo_src not in sys.path:
            sys.path.insert(0, omo_src)
        from omo.omo_belief import MOSBeliefManager

        manager = MOSBeliefManager(root=ROOT)
        do_id = manager.record_decision_outcome(
            decision_type=f"scene:{entry.get('scene_id', 'unknown')}",
            input_summary=f"run_id={entry.get('run_id', '')}",
            expected_outcome="scene execution to terminal",
            actual_outcome=f"adjudication={entry.get('adjudication', '')}",
            delta=entry.get("notes", "")[:200],
            source_run_id=entry.get("run_id", ""),
        )
        # Trust 校准链: outcome → capability_calibration (控制论反馈闭环)
        adjudication = entry.get("adjudication", "")
        success_rate = 1.0 if adjudication == "accepted" else 0.0 if adjudication == "rejected" else 0.5
        manager.record_capability_calibration(
            capability_ref=f"scene:{entry.get('scene_id', 'unknown')}",
            success_rate=success_rate,
            sample_size=1,
            last_run_id=entry.get("run_id", ""),
        )
        return do_id
    except Exception:
        return None  # MOS not configured, non-blocking


def list_outcomes(scene_id: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
    """List recent outcomes, optionally filtered by scene_id."""
    entries = read_jsonl(OUTCOME_LOG)
    if scene_id is not None:
        entries = [e for e in entries if e.get("scene_id") == scene_id]
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
