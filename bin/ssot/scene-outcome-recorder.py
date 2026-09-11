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
from pathlib import Path
from typing import Any

from _shared import ROOT, append_jsonl, load_yaml, read_jsonl, utc_now

OUTCOME_SCHEMA = "scene-outcome/v1"
OUTCOME_LOG = ROOT / ".omo" / "_knowledge" / "workflow-mesh" / "scene-outcomes.jsonl"
VALID_ADJUDICATIONS = {"accepted", "rejected", "revised"}
VALUE_EVIDENCE_LOG = ROOT / ".omo" / "_delivery" / "ingress" / "value-evidence.jsonl"
VERDICT_MAP = {"accepted": "accept", "revised": "edit", "rejected": "reject"}


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
    review_seconds: int | None = None,
    saved_seconds: int | None = None,
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

    # X3 价值证据桥: adjudication → value-evidence/v1 (裁决词汇 1:1 映射).
    # estimated_time_saved 以场景自主执行时长为估计值 (真实工作时长, 非合成).
    _write_value_evidence(entry, review_seconds=review_seconds, saved_seconds=saved_seconds)
    entry["value_evidence"] = True

    # North Star 信任链: adjudication → Outcome.Human.v1 → event-ledger.
    # North Star meter 只信任 broker-verified human outcomes.
    _write_event_ledger_outcome(entry, review_seconds=review_seconds, saved_seconds=saved_seconds)
    entry["north_star_bridge"] = True

    entry["status"] = "recorded"
    return entry


def _write_event_ledger_outcome(entry: dict[str, Any], *, review_seconds: int | None = None,
                                saved_seconds: int | None = None) -> None:
    """Bridge scene outcome to Outcome.Human.v1 in event-ledger (North Star source)."""
    try:
        import os as _os

        omo_src = str(ROOT / "projects" / "omo" / "src")
        if omo_src not in sys.path:
            sys.path.insert(0, omo_src)
        from omo.event_ledger.surface import EventLedgerSurface

        surface = EventLedgerSurface()
        verdict = VERDICT_MAP.get(entry.get("adjudication", ""), "reject")
        surface.append(
            event_type="Outcome.Human.v1",
            producer="scene-outcome-recorder",
            principal_id=_os.environ.get("OMO_PRINCIPAL_ID", "xiamingxing"),
            correlation_id=str(entry.get("run_id", "")),
            idempotency_key=f"scene:{entry.get('scene_id')}:{entry.get('run_id')}",
            payload={
                "verdict": verdict,
                "scene_id": entry.get("scene_id", ""),
                "run_id": entry.get("run_id", ""),
                "review_duration_seconds": review_seconds,
                "estimated_time_saved_seconds": saved_seconds,
                "source": "scene-outcome-bridge",
            },
        )
        surface.close()
    except Exception:
        pass  # North Star bridge is non-blocking


def _scene_run_duration_seconds(scene_id: str, run_id: str) -> int:
    """Read execution duration from calibration DB (real measured seconds)."""
    try:
        import sqlite3

        db = ROOT / "data" / "scene-metrics.db"
        if not db.exists():
            return 0
        conn = sqlite3.connect(str(db))
        try:
            row = conn.execute(
                "SELECT duration_ms FROM scene_execution WHERE scene_id=? AND run_id=? ORDER BY created_at DESC LIMIT 1",
                (scene_id, run_id),
            ).fetchone()
            return int(row[0] // 1000) if row and row[0] else 0
        finally:
            conn.close()
    except Exception:
        return 0


def _write_value_evidence(entry: dict[str, Any], *, review_seconds: int | None = None,
                          saved_seconds: int | None = None) -> None:
    """Bridge scene outcome to value-evidence/v1 (X3 data source).

    verdict: accepted→accept / revised→edit / rejected→reject (1:1).
    estimated_time_saved_seconds = scene autonomous work duration (from
    calibration DB) unless explicitly provided; review_duration_seconds
    is human-provided (0 = unknown).
    """
    try:
        import os

        scene_id = str(entry.get("scene_id", "unknown"))
        run_id = str(entry.get("run_id", ""))
        duration_s = _scene_run_duration_seconds(scene_id, run_id)
        review_s = int(review_seconds or 0)
        saved_s = int(saved_seconds if saved_seconds is not None else duration_s)

        evidence = {
            "schema": "value-evidence/v1",
            "timestamp": entry.get("ts", ""),
            "principal_id": os.environ.get("OMO_PRINCIPAL_ID", "xiamingxing"),
            "scene_id": scene_id,
            "run_id": run_id,
            "review_duration_seconds": review_s,
            "estimated_time_saved_seconds": saved_s,
            "verdict": VERDICT_MAP.get(entry.get("adjudication", ""), "reject"),
            "net_saved_seconds": max(0, saved_s - review_s),
            "qualifying": saved_s > review_s
            and entry.get("adjudication") in ("accepted", "revised"),
            "source": "scene-outcome-bridge",
        }
        VALUE_EVIDENCE_LOG.parent.mkdir(parents=True, exist_ok=True)
        append_jsonl(VALUE_EVIDENCE_LOG, evidence)
    except Exception:
        pass  # value bridge is non-blocking (X3 wiring must not break trust loop)


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
    rec_parser.add_argument("--review-seconds", type=int, default=None,
                            help="human review duration (X3 evidence; default: DB duration or 0)")
    rec_parser.add_argument("--saved-seconds", type=int, default=None,
                            help="estimated time saved (X3 evidence; default: scene work duration)")

    list_parser = sub.add_parser("list", help="list recent outcomes")
    list_parser.add_argument("--scene-id", default=None)
    list_parser.add_argument("--limit", type=int, default=20)

    args = parser.parse_args(argv)
    command = args.command or "list"

    if command == "record":
        result = record_outcome(
            args.scene_card,
            args.run_id,
            args.adjudication,
            actor=args.actor,
            notes=args.notes,
            revision_diff=args.revision_diff,
            review_seconds=args.review_seconds,
            saved_seconds=args.saved_seconds,
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
            print(f"  {e['ts'][:19]}  {e.get('scene_id', '?'):25s}  {e['adjudication']:10s}  by={e['actor']}")
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
