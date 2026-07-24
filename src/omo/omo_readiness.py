#!/usr/bin/env python3
"""OMO readiness snapshot — P63 governance readiness history log.

将 `bin/governance-readiness.py` 原本直接写 `.omo/_log/readiness-*.json` 的逻辑
迁入 OMO 内核,使其通过 brokered write surface,满足 direct-omo-io 约束.

提供:
  - Python API: write_readiness_snapshot(...)
  - CLI: omo readiness snapshot <payload-json>
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from omo.omo_io import AppendOnlyLog, write_text_atomic
from omo.omo_paths import find_omo_dir


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def write_readiness_snapshot(
    omo_dir: Path,
    *,
    score: int,
    grade: str,
    dimensions: dict[str, Any],
    thresholds: dict[str, int] | None = None,
    actor: str = "omo-readiness",
    source_ref: str = "omo:readiness:snapshot",
) -> Path:
    """写 readiness 历史快照到 .omo/_log/readiness-YYYYMMDD-HHMMSS.json.

    保留最近 30 个快照,避免目录膨胀.
    """
    log_dir = omo_dir / "_log"
    log_dir.mkdir(parents=True, exist_ok=True)

    now = datetime.now(UTC)
    timestamp = now.strftime("%Y%m%d-%H%M%S")
    iso = _utc_now()
    snap_path = log_dir / f"readiness-{timestamp}.json"

    # 清理旧快照,保留最近 30 个
    existing = sorted(log_dir.glob("readiness-*.json"), reverse=True)
    for old in existing[30:]:
        try:
            old.unlink()
        except Exception:  # defensive fallback
            pass

    snapshot = {
        "timestamp": iso,
        "score": score,
        "grade": grade,
        "phase": "P60+",
        "dimensions": dimensions,
        "thresholds": thresholds
        or {
            "A+_L4_stable": 90,
            "A_L3_mature": 80,
            "B_L2_basic": 70,
            "C_L1_starting": 60,
        },
        "actor": actor,
        "source_ref": source_ref,
    }
    write_text_atomic(snap_path, json.dumps(snapshot, indent=2, ensure_ascii=False))

    # P70: 同时追加到持久化 snapshots.jsonl (不受 30 快照 rotation 限制)
    persistent_log = log_dir / "readiness-snapshots.jsonl"
    try:
        AppendOnlyLog(persistent_log).append(snapshot, sort_keys=True)
    except Exception:  # defensive fallback
        pass

    return snap_path


def cmd_readiness_snapshot(omo_dir: Path, payload_json: str) -> int:
    """CLI: omo readiness snapshot '<json>'.

    payload 格式与 bin/governance-readiness.py 输出的 snapshot 一致.
    """
    try:
        payload = json.loads(payload_json)
    except json.JSONDecodeError as exc:
        print(f"❌ invalid JSON payload: {exc}", file=sys.stderr)
        return 1

    score = int(payload.get("score", 0))
    grade = str(payload.get("grade", ""))
    dimensions = payload.get("dimensions", {})
    thresholds = payload.get("thresholds")

    try:
        path = write_readiness_snapshot(
            omo_dir,
            score=score,
            grade=grade,
            dimensions=dimensions,
            thresholds=thresholds,
            actor="omo-readiness-cli",
            source_ref="omo:readiness:snapshot:cli",
        )
    except Exception as exc:  # defensive fallback
        print(f"❌ failed to write readiness snapshot: {exc}", file=sys.stderr)
        return 1

    print(f"✅ readiness snapshot written: {path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="omo readiness", description="OMO readiness history log"
    )
    sub = parser.add_subparsers(dest="command")
    snap = sub.add_parser("snapshot", help="Write a readiness snapshot to .omo/_log/")
    snap.add_argument("payload", help="Snapshot payload as JSON string")
    args = parser.parse_args(argv)
    if args.command != "snapshot":
        parser.print_help()
        return 1
    omo_dir = find_omo_dir()
    return cmd_readiness_snapshot(omo_dir, args.payload)


if __name__ == "__main__":
    raise SystemExit(main())
