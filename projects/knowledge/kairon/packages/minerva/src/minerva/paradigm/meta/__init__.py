"""Meta-Paradigm Engine — CLI bridge to Sophia (extracted package).

This module now uses CLI subprocess calls to Sophia instead of direct imports.
New code should call `sophia compile <query> --json` or `sophia learn suggest <query> --json` directly.

Install sophia: pip install sophia
"""

from __future__ import annotations

import json
import subprocess
from typing import Any, cast

# Re-export types and functions via subprocess bridge
__all__ = [
    "sophia_compile",
    "sophia_suggest",
    "sophia_evolve",
]


def sophia_compile(query: str, timeout: int = 30) -> dict[str, Any] | None:
    """Compile a paradigm via sophia CLI. Returns dict or None on failure."""
    try:
        result = subprocess.run(
            ["sophia", "compile", query[:500], "--json"],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode == 0:
            return cast("dict[str, Any] | None", json.loads(result.stdout))
    except Exception:
        pass
    return None


def sophia_suggest(query: str, timeout: int = 15) -> dict[str, Any]:
    """Suggest paradigm optimization via sophia CLI. Returns dict or empty sample."""
    try:
        result = subprocess.run(
            ["sophia", "learn", "suggest", query[:500], "--json"],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode == 0:
            return cast("dict[str, Any]", json.loads(result.stdout))
    except Exception:
        pass
    return {"sample_count": 0, "confidence": 0, "recommended_ops": [], "top_traces": []}


def sophia_evolve(query: str, timeout: int = 30) -> dict[str, Any] | None:
    """Get evolved paradigm via sophia CLI. Returns dict or None on failure."""
    try:
        result = subprocess.run(
            ["sophia", "evolve", query[:500]],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode == 0:
            return cast("dict[str, Any] | None", json.loads(result.stdout))
    except Exception:
        pass
    return None
