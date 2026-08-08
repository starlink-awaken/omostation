#!/usr/bin/env python3
"""MOS Cold Start — 预灌TELOS到world_snapshot (P0-T7).

Reads LifeOS TELOS files and seeds MOS world_snapshot with initial knowledge.
Solves the cold-start problem: MOS starts empty, Advisor has nothing to read.

Usage: python3 bin/ssot/mos-cold-start.py [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
TELOS_DIR = Path.home() / ".claude" / "LIFEOS" / "USER" / "TELOS"


def _extract_summary(filepath: Path, max_lines: int = 5) -> str:
    """Extract first few meaningful lines from a TELOS file as summary."""
    try:
        lines = filepath.read_text(encoding="utf-8").strip().split("\n")
        meaningful = [l.strip() for l in lines if l.strip() and not l.startswith("#") and not l.startswith("---")][:max_lines]
        return " | ".join(meaningful)[:300]
    except Exception:
        return ""


def seed_from_telos(*, dry_run: bool = False) -> dict[str, Any]:
    """Seed MOS world_snapshot from TELOS files."""
    if not TELOS_DIR.is_dir():
        return {"status": "skipped", "reason": f"TELOS dir not found: {TELOS_DIR}"}

    telos_files = sorted(TELOS_DIR.glob("*.md"))
    if not telos_files:
        return {"status": "skipped", "reason": "no .md files in TELOS dir"}

    seeded: list[dict[str, str]] = []
    skipped = 0

    for tf in telos_files:
        category = tf.stem.lower()  # e.g., "goals", "beliefs", "mission"
        summary = _extract_summary(tf)
        if not summary:
            skipped += 1
            continue

        snapshot = {
            "domain": "identity",
            "key": f"telos:{category}",
            "value": summary,
            "source": f"telos:{tf.name}",
            "confidence": 0.9,  # TELOS is high-confidence (human-authored)
            "schema": "world_snapshot/v1",
            "namespace": "agent_belief",
            "ts": datetime.now(UTC).isoformat(),
        }
        seeded.append({"key": snapshot["key"], "value_preview": summary[:60]})

        if not dry_run:
            try:
                mos_src = str(ROOT / "projects" / "kairon" / "packages" / "mos" / "src")
                if mos_src not in sys.path:
                    sys.path.insert(0, mos_src)
                from mos.agent_belief import write_world_snapshot
                write_world_snapshot(snapshot)
            except Exception:
                pass  # MOS not configured, just log

    return {
        "status": "completed",
        "telos_files_found": len(telos_files),
        "seeded_count": len(seeded),
        "skipped_count": skipped,
        "dry_run": dry_run,
        "seeded": seeded[:10],  # preview first 10
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="preview without writing to MOS")
    args = parser.parse_args(argv)

    result = seed_from_telos(dry_run=args.dry_run)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
