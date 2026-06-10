#!/usr/bin/env python3
"""Backward-compatible CLI for sync_omo_state.

Previously at scripts/sync_omo_state.py. This wrapper points to the
workspace-level script at ~/Workspace/scripts/sync_omo_state.py.
"""
from __future__ import annotations

import sys
from pathlib import Path

_workspace = Path.home() / "Workspace"
_script = _workspace / "scripts" / "sync_omo_state.py"

if not _script.exists():
    print(f"ERROR: {_script} not found. Run from a full workspace checkout.", file=sys.stderr)
    raise SystemExit(1)

# Inject workspace root so imports (omo.*) resolve
if str(_workspace) not in sys.path:
    sys.path.insert(0, str(_workspace))

exec(compile(_script.read_text(), _script, "exec"))
