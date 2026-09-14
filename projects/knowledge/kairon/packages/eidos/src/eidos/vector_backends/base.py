from __future__ import annotations

"""
---
Type: Module
Status: ACTIVE
Version: 1.0.0
Owner: '@Builder'
Layer: L3
Summary: "Base vector backend abstractions and vector search result schema."
Extracted from: SharedBrain D_Memory/organs/vector_backends/base.py → eidos/vector_backends/base.py
---
"""
# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Base ≡ Module
# 内涵 ≝ {Base}
# 外延 ≝ {e | e ∈ Eidos ∧ implements(e, Base)}
# 功能 ⊢ {Init_Base, Execute_Base, Validate_Base}
# =============================================================================


from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class VectorSearchResult:
    """Result from a vector similarity search."""

    entry_id: str
    content: str
    similarity: float
    metadata: dict[str, Any]
    distance: float | None = None


class VectorStoreBackend(ABC):
    """Abstract base class for vector storage backends."""

    def __init__(self, dimension: int = 384, db_path: str | None = None) -> None:
        """
        Initialize the vector store backend.

        Args:
            dimension: Vector dimensionality (default: 384 for sentence-transformers)
            db_path: Optional path for persistent storage
        """
        self.dimension = dimension
        self.db_path = db_path

    @abstractmethod
    def add(
        self,
        entry_id: str,
        vector: Any,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """
        Add a vector entry to the store.

        Args:
            entry_id: Unique identifier for the entry
            vector: Embedding vector (list or numpy array)
            content: Original text content
            metadata: Optional metadata dictionary
        """
        pass

    @abstractmethod
    def search(
        self,
        query_vector: Any,
        limit: int = 5,
        min_similarity: float = 0.0,
    ) -> list[VectorSearchResult]:
        """
        Search for similar vectors.

        Args:
            query_vector: Query embedding vector
            limit: Maximum number of results to return
            min_similarity: Minimum similarity threshold (0-1)

        Returns:
            List of VectorSearchResult, sorted by similarity (descending)
        """
        pass

    @abstractmethod
    def get(self, entry_id: str) -> VectorSearchResult | None:
        """
        Retrieve a specific entry by ID.

        Args:
            entry_id: Unique identifier

        Returns:
            VectorSearchResult if found, None otherwise
        """
        pass

    @abstractmethod
    def remove(self, entry_id: str) -> bool:
        """
        Remove an entry from the store.

        Args:
            entry_id: Unique identifier

        Returns:
            True if removed, False if not found
        """
        pass

    @abstractmethod
    def count(self) -> int:
        """
        Get the total number of entries in the store.

        Returns:
            Entry count
        """
        pass

    @abstractmethod
    def text_to_vector(self, text: str) -> list[float]:
        """
        Convert text to vector embedding.

        Args:
            text: Input text

        Returns:
            Vector embedding as list of floats
        """
        pass

    def health_check(self) -> dict[str, Any]:
        """
        Check backend health and status.

        Returns:
            Dictionary with health status information
        """
        try:
            count = self.count()
            return {
                "status": "healthy",
                "backend": self.__class__.__name__,
                "count": count,
                "dimension": self.dimension,
                "persistent": self.db_path is not None,
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "backend": self.__class__.__name__,
                "error": str(e),
            }
