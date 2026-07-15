"""cockpit wave2 — L3 entry for Wave2 dashboard / proposals (ADR-0190).

Delegates to c2g dashboard_export / governance_feedback / predictive_report
via subprocess — no business logic duplication.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
# commands → cockpit → src → project root (projects/cockpit)
_COCKPIT_ROOT = _SCRIPT_DIR.parent.parent.parent
_C2G_PROJECT = str((_COCKPIT_ROOT.parent / "c2g").resolve())
_WORKSPACE = _COCKPIT_ROOT.parent.parent  # projects/ → workspace


def _run_c2g_module(module: str, extra: list[str] | None = None) -> int:
    cmd = [
        "uv",
        "run",
        "--project",
        _C2G_PROJECT,
        "python",
        "-m",
        module,
    ]
    if extra:
        cmd.extend(extra)
    env = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith("VIRTUAL_ENV") and k != "PYTHONHOME"
    }
    # Prefer workspace runtime outcomes if present
    default_data = _WORKSPACE / "runtime" / "c2g" / "outcomes"
    if default_data.exists() and not any(
        a == "--data-dir" for a in (extra or [])
    ):
        cmd.extend(["--data-dir", str(default_data)])
    return subprocess.call(cmd, cwd=str(_WORKSPACE), env=env)


def cmd_wave2(args: argparse.Namespace) -> int:
    """Dispatch wave2 subcommands."""
    sub = getattr(args, "wave2_command", None) or "dashboard"
    rest = list(getattr(args, "wave2_args", None) or [])

    if sub in ("dashboard", "dash", "export"):
        extra = ["--pretty"] if getattr(args, "pretty", False) else []
        extra.extend(rest)
        return _run_c2g_module("c2g.dashboard_export", extra)
    if sub in ("proposals", "feedback"):
        return _run_c2g_module("c2g.governance_feedback", rest)
    if sub in ("predictive", "forecast"):
        return _run_c2g_module("c2g.predictive_report", rest)
    if sub == "help":
        print(
            "cockpit wave2 [dashboard|proposals|predictive] [-- ...]\n"
            "  dashboard   Wave2 JSON v1 (cards+heatmap+proposals)\n"
            "  proposals   governance_feedback proposals\n"
            "  predictive  forecast + heatmap markdown\n",
            file=sys.stderr,
        )
        return 0
    print(f"unknown wave2 subcommand: {sub}", file=sys.stderr)
    return 2
