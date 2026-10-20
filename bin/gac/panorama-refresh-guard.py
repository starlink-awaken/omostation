#!/usr/bin/env python3
"""Keep the Panorama collector job from silently stalling.

`com.omostation.panorama-dashboard-refresh` republishes
`runtime/dashboard/data.json`, which feeds the A9 gate and the Panorama
dashboard. launchd's KeepAlive covers a dead *process*; it does not cover a
job that has been booted out, and nothing else watches this output. Observed
2026-10-16 overnight: the job reported `state = uninitialized` / `runs = 0`
while data.json went 10.4h stale, and the cockpit watchdog stayed green
because it only probes :43191.

This guard treats the *artifact* as the contract: if the snapshot is missing
or older than the budget, kickstart the job and record why.

Manual check: `python3 bin/gac/panorama-refresh-guard.py --json --dry-run`
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

LABEL = "com.omostation.panorama-dashboard-refresh"
DATA_REL = Path("runtime") / "dashboard" / "data.json"
DEFAULT_MAX_AGE = 1800.0
LOG_REL = Path("runtime") / "cron" / "panorama-refresh-guard.log"


def code_root() -> Path:
    """Resolve the checkout root without hard-coding the machine path."""
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
        from repo_root import code_root as _code_root  # type: ignore[import-not-found]
        return Path(_code_root()).resolve()
    except Exception:  # noqa: BLE001 - locator is best-effort, cwd is the fallback
        return Path.cwd().resolve()


def max_age_seconds(raw: str | None) -> float:
    if raw is None or not raw.strip():
        return DEFAULT_MAX_AGE
    try:
        value = float(raw)
    except ValueError:
        raise SystemExit("PANORAMA_REFRESH_MAX_AGE must be a positive number of seconds")
    if value <= 0 or value != value or value == float("inf"):
        raise SystemExit("PANORAMA_REFRESH_MAX_AGE must be a positive number of seconds")
    return value


def snapshot_age(data: Path, now: float) -> float | None:
    try:
        return now - data.stat().st_mtime
    except OSError:
        return None


def kickstart(uid: int, dry_run: bool) -> tuple[bool, str]:
    domain = f"gui/{uid}/{LABEL}"
    if dry_run:
        return True, f"DRY_RUN kickstart {domain}"
    completed = subprocess.run(["launchctl", "kickstart", domain],
                               capture_output=True, text=True)
    if completed.returncode != 0:
        return False, f"kickstart failed: {(completed.stderr or completed.stdout).strip()}"
    return True, f"kickstart {domain}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit a JSON summary")
    parser.add_argument("--dry-run", action="store_true", help="report without kickstarting")
    parser.add_argument("--max-age", type=float, default=None,
                        help="staleness budget in seconds (default 1800)")
    args = parser.parse_args(argv)

    budget = args.max_age if args.max_age is not None else max_age_seconds(
        os.environ.get("PANORAMA_REFRESH_MAX_AGE"))
    root = code_root()
    data = root / DATA_REL
    now = time.time()
    age = snapshot_age(data, now)
    stale = age is None or age > budget

    action = "none"
    detail = f"age={age if age is None else round(age)}s budget={budget:g}s"
    if stale:
        ok, message = kickstart(os.getuid(), args.dry_run)
        action = "kickstarted" if ok else "kickstart_failed"
        detail = f"{message} ({detail})"

    log_path = root / LOG_REL
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S%z')} {action} {detail}\n")
    except OSError:
        pass

    summary = {"ok": not stale or action == "kickstarted", "action": action,
               "stale": stale, "age_seconds": age, "budget_seconds": budget,
               "data": str(data), "detail": detail}
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    elif stale:
        print(f"{action}: {detail}")
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
