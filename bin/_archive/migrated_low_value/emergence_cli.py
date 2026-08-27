#!/usr/bin/env python3
"""G-DEL.5b emergence + kill-switch ops CLI (ADR-0221).

Env (fail-closed defaults):
  ECOS_EMERGENCE_ENABLED=0|1   master enable (default 0)
  ECOS_EMERGENCE_WRITES=0|1    allow write side-effects (default 0)

Session kill flag file (optional multi-process):
  .omo/_delivery/emergence/session.kill

Usage:
  python3 bin/delivery/emergence_cli.py status
  python3 bin/delivery/emergence_cli.py detect --text "swarm consensus multi-agent vote"
  python3 bin/delivery/emergence_cli.py kill
  python3 bin/delivery/emergence_cli.py clear-kill
  python3 bin/delivery/emergence_cli.py measure
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from emergence import EmergenceDetector, KillSwitch, measure_emergence_accuracy  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
KILL_DIR = ROOT / ".omo" / "_delivery" / "emergence"
KILL_FLAG = KILL_DIR / "session.kill"


def _session_killed() -> bool:
    return KILL_FLAG.is_file()


def _make_switch(enabled: bool | None = None) -> KillSwitch:
    ks = KillSwitch(enabled=enabled)
    if _session_killed():
        ks.session_killed = True
    return ks


def cmd_status(_: argparse.Namespace) -> int:
    body = {
        "ECOS_EMERGENCE_ENABLED": os.environ.get("ECOS_EMERGENCE_ENABLED", "0"),
        "ECOS_EMERGENCE_WRITES": os.environ.get("ECOS_EMERGENCE_WRITES", "0"),
        "session_kill_flag": str(KILL_FLAG),
        "session_killed": _session_killed(),
        "allow_run": _make_switch().allow_run(),
        "allow_write": _make_switch().allow_write(),
        "adr": "0221",
        "note": "Default fail-closed: both env flags off until human enables.",
    }
    print(json.dumps(body, indent=2, ensure_ascii=False))
    return 0


def cmd_detect(args: argparse.Namespace) -> int:
    # Respect session kill file even when env enabled
    enabled = os.environ.get("ECOS_EMERGENCE_ENABLED", "0") == "1"
    if args.force_enable:
        enabled = True
    det = EmergenceDetector(_make_switch(enabled=enabled))
    pred = det.detect(args.text)
    print(
        json.dumps(
            {
                "ok": True,
                "text": args.text,
                "emergent": pred,
                "enabled": enabled,
                "session_killed": det.kill.session_killed,
                "allow_run": det.kill.allow_run(),
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


def cmd_kill(_: argparse.Namespace) -> int:
    KILL_DIR.mkdir(parents=True, exist_ok=True)
    KILL_FLAG.write_text(
        json.dumps(
            {
                "killed": True,
                "reason": "manual emergence_cli kill (ADR-0221 human intervention)",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"ok": True, "session_killed": True, "flag": str(KILL_FLAG)}))
    return 0


def cmd_clear_kill(_: argparse.Namespace) -> int:
    if KILL_FLAG.is_file():
        KILL_FLAG.unlink()
    print(json.dumps({"ok": True, "session_killed": False}))
    return 0


def cmd_measure(_: argparse.Namespace) -> int:
    # Harness path: enable detect, do not inherit leftover session kill file
    os.environ["ECOS_EMERGENCE_ENABLED"] = "1"
    if KILL_FLAG.is_file():
        KILL_FLAG.unlink()
    report = measure_emergence_accuracy()
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report.get("meets_gate") else 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("status")
    s.set_defaults(func=cmd_status)

    d = sub.add_parser("detect")
    d.add_argument("--text", required=True)
    d.add_argument(
        "--force-enable",
        action="store_true",
        help="detect with enabled=True for dry-run (still respects session kill)",
    )
    d.set_defaults(func=cmd_detect)

    k = sub.add_parser("kill", help="set session kill flag (multi-process)")
    k.set_defaults(func=cmd_kill)

    c = sub.add_parser("clear-kill")
    c.set_defaults(func=cmd_clear_kill)

    m = sub.add_parser("measure", help="run G-DEL.5b measure harness")
    m.set_defaults(func=cmd_measure)

    args = ap.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
