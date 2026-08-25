"""Cockpit Environment Resolver.

Dynamically discovers the workspace root and injects all subproject source directories
into sys.path, eliminating PYTHONPATH friction across the multi-repository workspace.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def get_workspace_root() -> Path:
    """Discovers the workspace root directory by locating projects/ and AGENTS.md."""
    for parent in Path(__file__).resolve().parents:
        if (parent / "projects").is_dir() and (parent / "AGENTS.md").exists():
            return parent
    # Fallback to current working directory or search upwards from cwd
    cwd = Path.cwd().resolve()
    for parent in [cwd, *cwd.parents]:
        if (parent / "projects").is_dir() and (parent / "AGENTS.md").exists():
            return parent
    return cwd


def setup_workspace_paths() -> Path:
    """Injects all subproject src/ directories into sys.path."""
    root = get_workspace_root()

    subproject_srcs = [
        root / "projects" / "omo" / "src",
        root / "projects" / "ecos" / "src",
        root / "projects" / "agora" / "src",
        root / "projects" / "cockpit" / "src",
        root / "projects" / "aetherforge" / "src",
        root / "projects" / "omlxc" / "src",
        root / "projects" / "bus-foundation" / "src",
        root / "projects" / "observability" / "src",
        root / "projects" / "metaos" / "src",
        root / "projects" / "l4-kernel" / "src",
        root / "projects" / "family-hub" / "src",
        root / "projects" / "model-driven" / "src",
        root / "lib",
        root / "bin",
    ]

    for p in subproject_srcs:
        p_str = str(p)
        if p.exists() and p_str not in sys.path:
            sys.path.insert(0, p_str)

    os.environ["WORKSPACE_ROOT"] = str(root)
    return root


# Auto-setup workspace paths upon import
_WORKSPACE_ROOT = setup_workspace_paths()
