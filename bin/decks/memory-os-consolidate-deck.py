#!/usr/bin/env python3
"""decks/memory-os-consolidate-deck.py — Memory OS sleep-time consolidate (Foundry)

Orchestrates `mos consolidate --dry-run` by default for safe cron; set
MOS_CONSOLIDATE_LIVE=1 to run without dry-run.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
RUNTIME_DIR = WORKSPACE / "runtime" / "omo" / "_delivery" / "foundry"
RUNTIME_DIR.mkdir(parents=True, exist_ok=True)


def main() -> int:
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    live = (os.environ.get("MOS_CONSOLIDATE_LIVE") or "").strip() in {"1", "true", "on"}
    cmd = [
        "uv",
        "run",
        "--directory",
        str(WORKSPACE / "projects" / "kairon"),
        "--package",
        "mos",
        "python",
        "-m",
        "mos",
        "consolidate",
        "--json",
    ]
    if not live:
        cmd.append("--dry-run")

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=900, cwd=str(WORKSPACE))
    except subprocess.TimeoutExpired:
        result = {
            "run_id": f"mos-consolidate-{run_id}",
            "ok": False,
            "error": "timeout",
            "live": live,
        }
        out = RUNTIME_DIR / f"mos-consolidate-{run_id}.json"
        out.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(json.dumps(result))
        return 1

    payload: dict
    try:
        payload = json.loads(proc.stdout.strip().splitlines()[-1]) if proc.stdout.strip() else {}
    except json.JSONDecodeError:
        payload = {"raw": proc.stdout[-2000:], "stderr": proc.stderr[-500:]}

    # dry-run with missing bun/gbrain is degraded but deck should not red-fail cron
    degraded = bool(payload.get("degraded"))
    ok = proc.returncode == 0 or degraded
    result = {
        "run_id": f"mos-consolidate-{run_id}",
        "timestamp": run_id,
        "ok": ok,
        "live": live,
        "returncode": proc.returncode,
        "result": payload,
        "stderr": (proc.stderr or "")[:400],
    }
    out = RUNTIME_DIR / f"mos-consolidate-{run_id}.json"
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    # metrics line
    metrics = RUNTIME_DIR / f"metrics-{run_id[:8]}.jsonl"
    with metrics.open("a", encoding="utf-8") as f:
        f.write(
            json.dumps(
                {
                    "deck": "memory-os-consolidate",
                    "ok": ok,
                    "live": live,
                    "duration_ms": payload.get("duration_ms"),
                    "ts": run_id,
                }
            )
            + "\n"
        )
    print(json.dumps({"ok": ok, "path": str(out), "degraded": degraded}, ensure_ascii=False))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
