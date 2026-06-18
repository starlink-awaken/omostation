"""Compatibility and path hacks for eCOS v5/v6 integration."""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Common Paths
WORKSPACE_ROOT = Path(os.environ.get("WORKSPACE", Path.home() / "Workspace"))
_AGORA_SRC = WORKSPACE_ROOT / "projects" / "agora" / "src"

def _ensure_agora_src() -> None:
    """确保 agora 源码路径在 sys.path 中，优先于安装版。"""
    if _AGORA_SRC.exists() and str(_AGORA_SRC) not in sys.path:
        sys.path.insert(0, str(_AGORA_SRC))
