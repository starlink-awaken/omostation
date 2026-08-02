"""Shared pytest configuration for Workflow Mesh integration tests.

Ensures that ECOS and OMO source paths are on sys.path so integration
tests can import from both submodules without manual path manipulation.
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
for _src in (
    _ROOT / "projects" / "omo" / "src",
    _ROOT / "projects" / "ecos" / "src",
):
    _p = str(_src)
    if _p not in sys.path:
        sys.path.insert(0, _p)
