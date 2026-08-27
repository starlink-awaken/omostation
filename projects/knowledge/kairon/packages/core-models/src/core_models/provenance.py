"""Alias module: re-exports Provenance for adapter compatibility.

Import path: from core_models.provenance import Provenance, ProvenanceEntry
"""

from __future__ import annotations

from core_models.models import Provenance

# Type alias — consumers use this as a TYPE_HINT.
ProvenanceEntry = Provenance

__all__ = ["Provenance", "ProvenanceEntry"]
