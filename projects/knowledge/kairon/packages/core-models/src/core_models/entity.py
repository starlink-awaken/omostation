"""Alias module: re-exports Entity and EntityType for adapter compatibility.

Import path: from core_models.entity import Entity, EntityType
"""

from __future__ import annotations

from core_models.models import Entity
from core_models.provenance import Provenance, ProvenanceEntry

# Type alias — consumers use this as a TYPE_HINT for entity types.
# The canonical set is ENTITY_TYPES in core_models.models.
EntityType = str

__all__ = ["Entity", "EntityType", "Provenance", "ProvenanceEntry"]
