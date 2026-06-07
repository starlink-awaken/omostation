"""AetherForge Gateway — path configuration.

Centralizes all filesystem paths to avoid hardcoding.
"""

from __future__ import annotations

from pathlib import Path

# Path to eCOS L0 MOF M1 compute_engine definitions
# Override via LLM_GATEWAY_M1_DIR env var if ecos repo is elsewhere
_M1_DIR_OVERRIDE = __import__("os").environ.get("LLM_GATEWAY_M1_DIR", "")

if _M1_DIR_OVERRIDE:
    M1_COMPUTE_ENGINE_DIR = Path(_M1_DIR_OVERRIDE)
else:
    M1_COMPUTE_ENGINE_DIR = (
        Path.home() / "Workspace" / "projects" / "ecos"
        / "src" / "ecos" / "ssot" / "mof" / "m1" / "compute_engine"
    )
