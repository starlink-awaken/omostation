"""
omo_bridge_interface — L0 ↔ L2 OMO 桥接契约
==============================================
Formalizes the exceptional L0→L2 dependency between ecos and omo.
All OMO interactions from ecos MUST go through this interface.

Usage:
    from ecos.ssot.tools.omo_bridge_interface import create_planned_task, write_yaml_atomic

Design:
    - Lazy-loads omo modules only when needed (--omo-to-m1 direction)
    - Provides typed stubs so callers don't need type: ignore
    - Isolated in a single file so the dependency surface is auditable
    - Testable via monkeypatch without importing omo
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

# ── OMO 源码路径 ──────────────────────────────────────────
# ecos project root is 5 levels up from this file
_ECOS_ROOT = (
    Path(__file__).resolve().parent.parent.parent.parent.parent
)  # projects/ecos
_WORKSPACE_ROOT = _ECOS_ROOT.parent.parent  # ~/Workspace
_OMO_SRC = _WORKSPACE_ROOT / "projects" / "omo" / "src"

if str(_OMO_SRC) not in sys.path:
    sys.path.insert(0, str(_OMO_SRC))

# ── Lazy module holders ───────────────────────────────────
_omo_ingress_mod = None
_omo_io_mod = None


def _load_omo_ingress():
    global _omo_ingress_mod
    if _omo_ingress_mod is None:
        from omo import omo_ingress as om  # type: ignore[reportMissingImports]

        _omo_ingress_mod = om
    return _omo_ingress_mod


def _load_omo_io():
    global _omo_io_mod
    if _omo_io_mod is None:
        from omo import omo_io as oi  # type: ignore[reportMissingImports]

        _omo_io_mod = oi
    return _omo_io_mod


# ── Public API ─────────────────────────────────────────────


def create_planned_task(*args: Any, **kwargs: Any) -> Any:
    """Create a planned task via OMO ingress.

    Delegates to omo.omo_ingress.create_planned_task.
    Only loads omo module on first call.
    """
    return _load_omo_ingress().create_planned_task(*args, **kwargs)


def write_yaml_atomic(path: Path, data: dict) -> None:
    """Atomically write a YAML file via OMO I/O.

    Delegates to omo.omo_io.write_yaml_atomic.
    Only loads omo module on first call.
    """
    return _load_omo_io().write_yaml_atomic(path, data)
