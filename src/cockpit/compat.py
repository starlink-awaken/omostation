"""Compatibility shims for eCOS v6 integration."""

from __future__ import annotations

import os
from pathlib import Path


def _discover_workspace_root() -> Path:
    configured = os.environ.get("WORKSPACE_ROOT") or os.environ.get("WORKSPACE")
    if configured:
        return Path(configured).expanduser()

    for parent in Path(__file__).resolve().parents:
        if (parent / "docs" / "project-registry.yaml").is_file():
            return parent
    return Path.home() / "Workspace"


WORKSPACE_ROOT = _discover_workspace_root()
