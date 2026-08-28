"""Cockpit ops subcommand — delegates to bin/ops/cli.py (Service Gateway).

This module bridges the cockpit CLI with the standalone ops CLI, allowing
users to run `cockpit ops status` instead of `python3 bin/ops/cli.py status`.
"""

from __future__ import annotations

import sys
from argparse import Namespace
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[3]
OPS_CLI = WORKSPACE / "bin" / "ops" / "cli.py"


def cmd_ops(args: Namespace) -> int:
    """Dispatch ops subcommand to bin/ops/cli.py."""
    # Build the argument list for the ops CLI
    ops_args = []

    action = getattr(args, "ops_action", "status")
    if action == "status":
        ops_args = ["status"]
        if getattr(args, "json", False):
            ops_args.append("--json")
    elif action == "up":
        ops_args = ["up"]
        if getattr(args, "service", None):
            ops_args.append(args.service)
        if getattr(args, "dry_run", False):
            ops_args.append("--dry-run")
    elif action == "down":
        ops_args = ["down"]
        if getattr(args, "service", None):
            ops_args.append(args.service)
        if getattr(args, "dry_run", False):
            ops_args.append("--dry-run")
    elif action == "deploy":
        ops_args = ["deploy"]
        if getattr(args, "profile", "full"):
            ops_args.extend(["--profile", args.profile])
    elif action == "deps":
        ops_args = ["deps"]
        if getattr(args, "service", None):
            ops_args.append(args.service)
    elif action == "logs":
        ops_args = ["logs"]
        if getattr(args, "service", None):
            ops_args.append(args.service)
        ops_args.extend(["-n", str(getattr(args, "lines", 50))])
    elif action == "summary":
        ops_args = ["summary"]
    elif action == "discover":
        ops_args = ["discover"]
        if getattr(args, "update", False):
            ops_args.append("--update")
    elif action == "validate":
        ops_args = ["validate"]
        if getattr(args, "service", None):
            ops_args.append(args.service)
    elif action == "generate":
        ops_args = ["generate"]
        ops_args.extend(["--format", getattr(args, "format", "docker-compose")])
        if getattr(args, "output", None):
            ops_args.extend(["--output", args.output])
    else:
        ops_args = [action]

    # Import and run the ops CLI
    try:
        sys.path.insert(0, str(WORKSPACE))
        from bin.ops.cli import main as ops_main

        # Reconstruct sys.argv for the ops CLI
        old_argv = sys.argv
        sys.argv = ["ops"] + ops_args
        try:
            return ops_main()
        finally:
            sys.argv = old_argv
    except ImportError as e:
        print(f"ERROR: Failed to import ops CLI: {e}", file=sys.stderr)
        return 1
    except SystemExit as e:
        return e.code if isinstance(e.code, int) else 0
