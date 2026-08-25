"""cockpit.commands.watchdog — Autonomous daemon watchdog & supervisor command."""

from __future__ import annotations

import argparse
import runpy
import sys
from pathlib import Path


def cmd_watchdog(args: argparse.Namespace) -> int:
    """Dispatches the daemon watchdog prober or supervisor loop."""
    from cockpit.env_resolver import get_workspace_root

    ws = get_workspace_root()
    script = ws / "bin" / "gac" / "daemon-watchdog.py"
    if not script.is_file():
        sys.stderr.write(f"Error: watchdog script not found at {script}\n")
        return 1

    watchdog_args = ["daemon-watchdog"]
    if getattr(args, "probe", False):
        watchdog_args.append("--probe")
    if getattr(args, "json", False):
        watchdog_args.append("--json")
    if getattr(args, "interval", None) is not None:
        watchdog_args.extend(["--interval", str(args.interval)])

    old_argv = sys.argv
    try:
        sys.argv = watchdog_args
        runpy.run_path(str(script), run_name="__main__")
        return 0
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 0
    except Exception as exc:
        sys.stderr.write(f"Watchdog error: {exc}\n")
        return 1
    finally:
        sys.argv = old_argv
