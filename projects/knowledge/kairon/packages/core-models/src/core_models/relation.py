"""Alias module: re-exports Relation and RelationType for adapter compatibility.

Import path: from core_models.relation import Relation, RelationType
"""

from __future__ import annotations

from core_models.models import Relation

# Type alias — consumers use this as a TYPE_HINT for relation types.
# The canonical dict is RELATION_TYPES in core_models.models.
RelationType = str

__all__ = ["Relation", "RelationType"]
