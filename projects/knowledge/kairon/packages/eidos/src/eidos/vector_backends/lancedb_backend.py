from __future__ import annotations

from typing import Any, cast

"""
---
Type: Module
Status: ACTIVE
Version: 1.0.0
Owner: '@Builder'
Authority: organs/D-Memory/AGENTS.md
Layer: L3
Summary: "Optional LanceDB-backed vector storage implementation."
---
"""
# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Lancedb Backend ≡ Module
# 内涵 ≝ {Lancedb, Backend}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, LancedbBackend)}
# 功能 ⊢ {Lancedb_Backend, Init_Lancedb, Validate_Backend}
# =============================================================================

import logging
import os
import time

from eidos.base import VectorSearchResult, VectorStoreBackend  # type: ignore[reportMissingImports]

_log = logging.getLogger(__name__)

# Optional dependencies - will be None if not installed
try:
    import lancedb
    from sentence_transformers import SentenceTransformer

    LANCEDB_AVAILABLE = True
except ImportError:
    lancedb: Any = None  # type: ignore[no-redef]
    SentenceTransformer: Any = None  # type: ignore[no-redef]
    LANCEDB_AVAILABLE = False


class LanceDBBackend(VectorStoreBackend):
    """
    High-performance vector store using LanceDB + sentence-transformers.

    Features:
    - Semantic embeddings (all-MiniLM-L6-v2, 384 dimensions)
    - IVF-PQ indexing for large-scale datasets
    - Persistent disk-based storage
    - Role-based table isolation

    Note: This backend requires optional dependencies and will raise
    RuntimeError if used without proper installation.
    """

    def __init__(self, dimension: int = 384, db_path: str | None = None, role: str = "default") -> None:
        """
        Initialize LanceDB backend.

        Args:
            dimension: Vector dimension (default: 384 for all-MiniLM-L6-v2)
            db_path: Base directory for LanceDB databases
            role: Logical role name for table isolation

        Raises:
            RuntimeError: If LanceDB or sentence-transformers not installed
        """
        if not LANCEDB_AVAILABLE:
            msg = "LanceDB backend requires lancedb>=0.5.0 and sentence-transformers>=2.3.0"
            raise RuntimeError(msg)

        super().__init__(dimension=dimension, db_path=db_path)
        self.role = role.lower().replace(" ", "_").replace("-", "_")
        self.base_dir = db_path or os.path.join(os.getcwd(), "data", "vector_memories")

        # Create base directory
        try:
            os.makedirs(self.base_dir, exist_ok=True)
        except OSError as e:
            _log.error(f"Failed to create LanceDB directory at {self.base_dir}: {e}")
            raise

        # Lazy load embedding model and database connection
        self._model: SentenceTransformer | None = None  # type: ignore[reportInvalidTypeForm]
        self._table: Any | None = None

    def _get_model(self) -> SentenceTransformer:  # type: ignore[reportInvalidTypeForm]
        """Lazy-load the sentence transformer model."""
        if self._model is None:
            _log.info("🧠 Loading sentence-transformers model (all-MiniLM-L6-v2)...")
            self._model = SentenceTransformer("all-MiniLM-L6-v2")
        return self._model

    def _get_table(self) -> Any:
        """Get or create LanceDB table for this role."""
        if self._table is not None:
            return self._table

        db_path = os.path.join(self.base_dir, self.role)
        db = lancedb.connect(db_path)

        # Check if table exists
        if "memories" not in db.list_tables():
            import pyarrow as pa

            schema = pa.schema(
                [
                    pa.field("id", pa.string()),
                    pa.field("vector", pa.list_(pa.float32(), self.dimension)),
                    pa.field("content", pa.string()),
                    pa.field("timestamp", pa.float64()),
                ]
            )
            self._table = db.create_table("memories", schema=schema)
        else:
            self._table = db.open_table("memories")

        return self._table

    def _ensure_index(self, table: Any) -> None:
        """Create or update IVF-PQ index for large datasets."""
        count = table.count_rows()
        if count >= 1000:
            try:
                _log.info(f"⚡ [LanceDB] Optimizing IVF-PQ index for {count} records...")
                table.create_index(
                    metric="L2",
                    num_partitions=256,
                    num_sub_vectors=96,  # 384/4
                    replace=True,
                )
                _log.info("✅ [LanceDB] IVF-PQ index created/updated.")
            except Exception as e:
                _log.warning(f"Failed to create LanceDB index: {e}")

    # ------------------------------------------------------------------
    # Text → Vector (semantic embeddings)
    # ------------------------------------------------------------------

    def text_to_vector(self, text: str) -> list[float]:
        """
        Convert text to semantic embedding vector.

        Uses sentence-transformers all-MiniLM-L6-v2 model.
        """
        model = self._get_model()
        vector = model.encode(text)
        return vector.tolist()

    # ------------------------------------------------------------------
    # CRUD operations
    # ------------------------------------------------------------------

    def add(
        self,
        entry_id: str,
        vector: list[float] | object,
        content: str,
        metadata: dict[str, object] | None = None,
    ) -> None:
        """Add a vector entry to LanceDB."""
        table = self._get_table()

        # LanceDB expects specific format
        table.add(
            [
                {
                    "id": entry_id,
                    "vector": vector,
                    "content": content,
                    "timestamp": time.time(),
                }
            ]
        )

        # Auto-create index if needed
        self._ensure_index(table)

    def search(
        self,
        query_vector: list[float] | object,
        limit: int = 5,
        min_similarity: float = 0.0,
    ) -> list[VectorSearchResult]:
        """Search for similar vectors using LanceDB."""
        table = self._get_table()

        try:
            # Execute vector search
            results = table.search(query_vector).limit(limit).to_list()

            # Convert to VectorSearchResult format
            formatted = []
            for r in results:
                # LanceDB returns distance (lower is better)
                # Convert to similarity: similarity = 1 / (1 + distance)
                distance = r.get("_distance", 0.0)
                similarity = 1.0 / (1.0 + distance)

                if similarity < min_similarity:
                    continue

                formatted.append(
                    VectorSearchResult(
                        entry_id=r["id"],
                        content=r["content"],
                        similarity=similarity,
                        metadata={},
                        distance=distance,
                    )
                )
            return formatted
        except (TypeError, ValueError, AttributeError, RuntimeError) as e:
            _log.error(f"LanceDB search failed: {e}")
            return []

    def get(self, entry_id: str) -> VectorSearchResult | None:
        """Retrieve a specific entry by ID."""
        # LanceDB doesn't have a simple get by ID API
        # We need to search with a limit of 1 and filter
        # For now, return None (can be implemented if needed)
        _log.warning(f"LanceDBBackend.get() not implemented for entry_id={entry_id}")
        return None

    def remove(self, entry_id: str) -> bool:
        """Remove an entry from LanceDB."""
        try:
            table = self._get_table()
            table.delete(f"id = '{entry_id}'")
            return True
        except Exception as e:
            _log.error(f"Failed to delete entry {entry_id}: {e}")
            return False

    def count(self) -> int:
        """Get the total number of entries."""
        table = self._get_table()
        return cast("int", table.count_rows())

    def health_check(self) -> dict[str, Any]:
        """Check backend health."""
        base_status = super().health_check()
        if base_status["status"] == "healthy":
            base_status["backend_type"] = "lancedb"
            base_status["embedding_type"] = "semantic_sentence_transformers"
            base_status["role"] = self.role
        return cast("dict[str, Any]", base_status)
