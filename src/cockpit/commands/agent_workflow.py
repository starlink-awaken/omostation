"""Cockpit entrypoint for executable agent governance workflows."""

from __future__ import annotations

import subprocess
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[5]


def cmd_agent_workflow(args) -> int:
    """Delegate to the workspace agent-workflow runner."""
    forwarded = list(getattr(args, "agent_workflow_args", []) or [])
    if not forwarded:
        forwarded = ["list"]
    command = [
        "uv",
        "run",
        "--with",
        "pyyaml",
        "python",
        str(WORKSPACE / "bin" / "agent-workflow.py"),
        *forwarded,
    ]
    return subprocess.call(command, cwd=str(WORKSPACE))
