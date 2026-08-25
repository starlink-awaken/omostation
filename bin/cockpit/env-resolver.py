#!/usr/bin/env python3
"""
Root Environment Resolver (ADR-0427 / Phase 8)
==============================================
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
    return Path.cwd().resolve()


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


# Auto-setup when imported
_WORKSPACE_ROOT = setup_workspace_paths()


def main():
    """CLI dispatcher: executes a module with the full workspace environment loaded."""
    if len(sys.argv) < 2:
        print("Usage: python3 env-resolver.py <module_or_script> [args...]")
        print(f"Workspace Root: {_WORKSPACE_ROOT}")
        print(f"Active sys.path entries ({len(sys.path)}):")
        for p in sys.path[:8]:
            print(f"  • {p}")
        sys.exit(0)

    target = sys.argv[1]
    sys.argv = sys.argv[1:]

    if target.endswith(".py"):
        import runpy
        runpy.run_path(target, run_name="__main__")
    else:
        import runpy
        runpy.run_module(target, run_name="__main__")


if __name__ == "__main__":
    main()
