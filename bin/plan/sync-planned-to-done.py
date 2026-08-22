#!/usr/bin/env python3
"""sync-planned-to-done — close planned/candidate tasks whose parent BET is done.

Phase 49 / ISC-3 health anomaly root cause:
  compass_radar reads `.omo/tasks/planned/*.yaml` priority/risk/owner metrics.
  `bin/_archive/c2g/strategy.py::_check_anomalies` flags any pending P0 > 5 as
  WARN, dropping governance_anomaly_score to 25 (熔断) and capping health_score
  at 28/100. Of the 44 P0 candidates sitting in planned/, 43 are stale
  duplicates whose parent BET is `done` in `docs/plans/3y-bet-ledger.yaml`.

This tool reconciles the two views:
  - reads done-set from `docs/plans/3y-bet-ledger.yaml`
  - scans `.omo/tasks/planned/` for status=candidate + matching BET
  - sets status=done, appends `closed_reason: parent-bet-done`,
    sets `done_at: <utc>` and `source: planned-to-done-sync`
  - moves the file to `.omo/tasks/archived/done/` (tracked cold tree, per
    task-archive.py convention)

Safe-by-default: dry-run unless --apply. Tracks file moves with `git mv`
so rename detection stays intact.

Exit codes:
  0 success / dry-run done
  1 config error
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
TASKS = WORKSPACE / ".omo" / "tasks"
PLANNED = TASKS / "planned"
COLD_DONE = TASKS / "archived" / "done"
LEDGER = WORKSPACE / "docs" / "plans" / "3y-bet-ledger.yaml"


def load_done_bets(ledger: Path) -> set[str]:
    """Yield every BET id whose status is `done` in the multi-doc ledger."""
    import yaml

    done: set[str] = set()
    docs = list(yaml.safe_load_all(ledger.read_text(encoding="utf-8")))
    if not docs:
        return done
    last = docs[-1] or {}
    for bet in last.get("bets", []):
        if bet.get("status") == "done" and "id" in bet:
            done.add(bet["id"])
    return done


def scan_stale_candidates(done_bets: set[str], planned_dir: Path) -> list[Path]:
    """Return planned/*.yaml files where id is in done_bets and status=candidate."""
    import yaml

    stale: list[Path] = []
    if not planned_dir.is_dir():
        return stale
    for path in sorted(planned_dir.glob("*.yaml")):
        try:
            t = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError:
            continue
        if not isinstance(t, dict):
            continue
        tid = t.get("id", "")
        if tid in done_bets and t.get("status") == "candidate":
            stale.append(path)
    return stale


def stamp_close(path: Path, now_iso: str) -> None:
    """In-place mutate: status=done, closed_reason, done_at, source."""
    import yaml

    text = path.read_text(encoding="utf-8")
    t = yaml.safe_load(text) or {}
    t["status"] = "done"
    t["closed_reason"] = "parent-bet-done"
    t["done_at"] = now_iso
    t["source"] = t.get("source", "3y-bet-ledger")
    t["source"] = f"{t['source']}+planned-to-done-sync"
    path.write_text(
        yaml.dump(t, allow_unicode=True, default_flow_style=False, sort_keys=False),
        encoding="utf-8",
    )


def git_mv(src: Path, dst: Path) -> tuple[bool, str]:
    """Prefer `git mv` so the index records a rename; fall back to shutil.move."""
    try:
        proc = subprocess.run(
            ["git", "mv", str(src), str(dst)],
            cwd=WORKSPACE,
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode == 0:
            return True, "git mv"
    except FileNotFoundError:
        pass
    shutil.move(str(src), str(dst))
    return False, "shutil.move (git mv unavailable)"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--apply", action="store_true", help="Execute moves (default: dry-run)")
    p.add_argument(
        "--json",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Emit machine-readable summary (default: true)",
    )
    args = p.parse_args(argv)

    if not LEDGER.is_file():
        print(f"error: missing {LEDGER}", file=sys.stderr)
        return 1
    if not PLANNED.is_dir():
        print(f"error: missing {PLANNED}", file=sys.stderr)
        return 1

    now_iso = datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
    done_bets = load_done_bets(LEDGER)
    stale = scan_stale_candidates(done_bets, PLANNED)

    summary: dict = {
        "ts": now_iso,
        "ledger": str(LEDGER),
        "planned_dir": str(PLANNED),
        "cold_dest": str(COLD_DONE),
        "apply": bool(args.apply),
        "done_bet_count": len(done_bets),
        "stale_candidate_count": len(stale),
        "stale_ids": [p.stem for p in stale],
    }

    if not args.apply:
        if args.json:
            print(json.dumps(summary, ensure_ascii=False, indent=2))
        else:
            print(
                f"dry-run: {len(stale)} stale candidate(s) in planned/ match done BETs; "
                f"re-run with --apply to close."
            )
        return 0

    COLD_DONE.mkdir(parents=True, exist_ok=True)
    results: list[dict] = []
    for src in stale:
        stamp_close(src, now_iso)
        dst = COLD_DONE / src.name
        if dst.exists():
            stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
            dst = COLD_DONE / f"{src.stem}.merged-{stamp}{src.suffix}"
        moved_with_git, mode = git_mv(src, dst)
        results.append(
            {
                "id": src.stem,
                "src": str(src.relative_to(WORKSPACE)),
                "dst": str(dst.relative_to(WORKSPACE)),
                "mode": mode,
            }
        )
    summary["results"] = results
    summary["closed_count"] = len(results)

    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(f"closed {len(results)} stale candidate(s):")
        for r in results:
            print(f"  {r['id']}  ({r['mode']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())