from __future__ import annotations

"""
---
Type: Module
Status: ACTIVE
Version: 1.0.0
Owner: '@Builder'
Authority: organs/D-Memory/AGENTS.md
Layer: L3
Summary: "Vector backend factory with automatic LanceDB-to-NumPy fallback."
Extracted from: SharedBrain D_Memory/organs/vector_backends/factory.py → eidos/vector_backends/factory.py
---
"""
# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Factory ≡ Module
# 内涵 ≝ {Factory}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, Factory)}
# 功能 ⊢ {Init_Factory, Execute_Factory, Validate_Factory}
# =============================================================================


import logging
import os
from typing import Any

from .base import VectorStoreBackend
from .lancedb_backend import LANCEDB_AVAILABLE, LanceDBBackend
from .numpy_backend import NumPyBackend

_log = logging.getLogger(__name__)


def create_vector_backend(
    dimension: int = 384,
    db_path: str | None = None,
    role: str = "default",
    backend_preference: str | None = None,
) -> VectorStoreBackend:
    """
    Create a vector backend with automatic fallback.

    Selection logic:
    - If backend_preference is specified, use that (or raise error if unavailable)
    - If "auto" (default), try LanceDB first, fall back to NumPy
    - Environment variable BOS_VECTOR_BACKEND overrides preference

    Args:
        dimension: Vector dimensionality
        db_path: Database path for persistence
        role: Logical role name (for LanceDB table isolation)
        backend_preference: Force specific backend ("lancedb", "numpy", or "auto")

    Returns:
        VectorStoreBackend instance

    Raises:
        ValueError: If specified backend is unavailable
    """
    # Check environment override
    env_backend = os.environ.get("BOS_VECTOR_BACKEND", "").lower()
    if env_backend:
        backend_preference = env_backend

    # Normalize preference
    if backend_preference is None or backend_preference == "auto":
        backend_preference = "auto"

    # Try LanceDB first if allowed
    if backend_preference in ("auto", "lancedb"):
        if LANCEDB_AVAILABLE:
            try:
                _log.info("🚀 Using LanceDB backend (semantic search)")
                return LanceDBBackend(dimension=dimension, db_path=db_path, role=role)
            except Exception as e:
                if backend_preference == "lancedb":
                    # User explicitly requested LanceDB
                    msg = f"LanceDB backend requested but failed to initialize: {e}"
                    raise RuntimeError(msg) from e
                _log.warning(f"⚠️  LanceDB initialization failed, falling back to NumPy: {e}")
        elif backend_preference == "lancedb":
            msg = "LanceDB backend requested but dependencies not installed. Install with: pip install lancedb>=0.5.0 sentence-transformers>=2.3.0"
            raise RuntimeError(msg)

    # Fall back to NumPy
    _log.info("🔷 Using NumPy backend (zero-dependency)")
    return NumPyBackend(dimension=dimension, db_path=db_path)


def get_backend_info() -> dict[str, Any]:
    """
    Get information about available backends.

    Returns:
        Dictionary with backend availability and recommendations
    """
    info = {
        "numpy_available": True,  # Always available (required dependency)
        "lancedb_available": LANCEDB_AVAILABLE,
        "recommended_backend": "lancedb" if LANCEDB_AVAILABLE else "numpy",
        "current_preference": os.environ.get("BOS_VECTOR_BACKEND", "auto"),
    }

    if not LANCEDB_AVAILABLE:
        info["lancedb_install_hint"] = (
            "For enhanced semantic search, install optional dependencies:\n"
            "  pip install lancedb>=0.5.0 sentence-transformers>=2.3.0"
        )

    return info
