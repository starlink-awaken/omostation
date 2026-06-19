"""Compatibility shims for eCOS v5/v6 integration."""
from __future__ import annotations

import os
from pathlib import Path

# Common Paths
WORKSPACE_ROOT = Path(os.environ.get("WORKSPACE", Path.home() / "Workspace"))
