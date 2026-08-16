from __future__ import annotations

"""
---
Type: Module
Status: ACTIVE
Version: 1.0.0
Owner: '@Builder'
Authority: organs/D-Memory/AGENTS.md
Layer: L3
Summary: "Default NumPy-plus-SQLite vector storage backend."
---
"""
# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Numpy Backend ≡ Module
# 内涵 ≝ {Numpy, Backend}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, NumpyBackend)}
# 功能 ⊢ {Numpy_Backend, Init_Numpy, Validate_Backend}
# =============================================================================

import hashlib
import json
import logging
import threading
from typing import Any, cast

import numpy as np

from eidos.base import VectorSearchResult, VectorStoreBackend  # type: ignore[reportMissingImports]
from eidos.organs.storage_dal import SQLiteOperationalError, SQLiteRelationalProvider

_log = logging.getLogger(__name__)


class NumPyBackend(VectorStoreBackend):
    """
    Zero-dependency vector store using NumPy + SQLite.

    Features:
    - Deterministic hash embeddings (no external ML model)
    - Cosine similarity search
    - Thread-safe operations
    - SQLite WAL persistence
    """

    def __init__(self, dimension: int = 384, db_path: str | None = None) -> None:
        super().__init__(dimension=dimension, db_path=db_path)
        self._vectors: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()
        self._provider: SQLiteRelationalProvider | None = None

        if db_path is not None:
            self._provider = SQLiteRelationalProvider(db_path)
            self._load_from_db()

    # ------------------------------------------------------------------
    # Text → Vector (deterministic hash-based)
    # ------------------------------------------------------------------

    def text_to_vector(self, text: str) -> list[float]:
        """
        Deterministic hash-based embedding.

        SHA-256 of text is expanded to fill dimension,
        mapped to [-1, 1] floats, then L2-normalized.
        """
        digest = hashlib.sha256(text.encode("utf-8")).digest()  # 32 bytes

        # Expand hash to cover the full dimension
        repeated = digest
        while len(repeated) < self.dimension:
            repeated += hashlib.sha256(repeated).digest()
        raw_bytes = repeated[: self.dimension]

        # Interpret as uint8 → float32 in [-1, 1]
        vec = np.frombuffer(raw_bytes, dtype=np.uint8).astype(np.float32)
        vec = (vec / 127.5) - 1.0  # map [0, 255] → [-1, 1]

        # L2 normalize to unit vector
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return cast("list[float]", vec.tolist())

    # ------------------------------------------------------------------
    # CRUD operations
    # ------------------------------------------------------------------

    def add(
        self,
        entry_id: str,
        vector: Any,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Add a vector entry to the store."""
        # Convert to numpy array if needed
        if isinstance(vector, list):
            vector = np.array(vector, dtype=np.float32)
        elif not isinstance(vector, np.ndarray):
            vector = np.array(vector, dtype=np.float32)

        if vector.shape != (self.dimension,):
            msg = f"Expected vector of dimension {self.dimension}, got {vector.shape}"
            raise ValueError(msg)

        with self._lock:
            self._vectors[entry_id] = {
                "vector": vector,
                "content": content,
                "metadata": metadata or {},
            }
            if self.db_path is not None:
                self._persist_entry(entry_id)

    def search(
        self,
        query_vector: Any,
        limit: int = 5,
        min_similarity: float = 0.0,
    ) -> list[VectorSearchResult]:
        """Search for similar vectors using cosine similarity."""
        if not self._vectors:
            return []

        # Convert query to numpy array
        if isinstance(query_vector, list):
            query_vector = np.array(query_vector, dtype=np.float32)
        elif not isinstance(query_vector, np.ndarray):
            query_vector = np.array(query_vector, dtype=np.float32)

        # Build matrix and compute similarities
        entry_ids = list(self._vectors.keys())
        matrix = np.vstack([self._vectors[eid]["vector"] for eid in entry_ids])

        # Cosine similarity: dot product of normalized vectors
        norms = np.linalg.norm(matrix, axis=1)
        query_norm = np.linalg.norm(query_vector)
        similarities = np.dot(matrix, query_vector) / (norms * query_norm + 1e-10)

        # Sort by similarity (descending)
        results = []
        for idx in np.argsort(similarities)[::-1]:
            sim = float(similarities[idx])
            if sim < min_similarity:
                break
            eid = entry_ids[idx]
            entry = self._vectors[eid]
            results.append(
                VectorSearchResult(
                    entry_id=eid,
                    content=entry["content"],
                    similarity=sim,
                    metadata=entry["metadata"],
                    distance=1.0 - sim,  # Convert similarity to distance
                )
            )
            if len(results) >= limit:
                break
        return results

    def get(self, entry_id: str) -> VectorSearchResult | None:
        """Retrieve a specific entry by ID."""
        entry = self._vectors.get(entry_id)
        if entry is None:
            return None
        return VectorSearchResult(
            entry_id=entry_id,
            content=entry["content"],
            similarity=1.0,  # Self-similarity is perfect
            metadata=entry["metadata"],
        )

    def remove(self, entry_id: str) -> bool:
        """Remove an entry from the store."""
        with self._lock:
            if entry_id not in self._vectors:
                return False
            del self._vectors[entry_id]
            if self.db_path is not None:
                self._delete_entry(entry_id)
            return True

    def count(self) -> int:
        """Get the total number of entries."""
        return len(self._vectors)

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------

    def _persist_entry(self, entry_id: str) -> None:
        """Persist a single entry to SQLite."""
        assert self._provider is not None
        self._provider.execute("PRAGMA journal_mode=WAL")
        self._provider.execute(
            "CREATE TABLE IF NOT EXISTS vectors ("
            "  entry_id TEXT PRIMARY KEY,"
            "  vector BLOB NOT NULL,"
            "  content TEXT NOT NULL,"
            "  metadata TEXT NOT NULL"
            ")"
        )
        entry = self._vectors[entry_id]
        self._provider.execute(
            "INSERT OR REPLACE INTO vectors (entry_id, vector, content, metadata) VALUES (?, ?, ?, ?)",
            (
                entry_id,
                entry["vector"].astype(np.float32).tobytes(),
                entry["content"],
                json.dumps(entry["metadata"]),
            ),
        )

    def _delete_entry(self, entry_id: str) -> None:
        """Delete an entry from SQLite."""
        assert self._provider is not None
        self._provider.execute("DELETE FROM vectors WHERE entry_id = ?", (entry_id,))

    def _load_from_db(self) -> None:
        """Load all entries from SQLite."""
        assert self._provider is not None
        import os

        if not os.path.exists(self.db_path):
            return

        self._provider.execute("PRAGMA journal_mode=WAL")
        try:
            rows = self._provider.fetch_all("SELECT entry_id, vector, content, metadata FROM vectors")
        except SQLiteOperationalError:
            return

        for row in rows:
            vec = np.frombuffer(row["vector"], dtype=np.float32).copy()
            if vec.shape == (self.dimension,):
                self._vectors[row["entry_id"]] = {
                    "vector": vec,
                    "content": row["content"],
                    "metadata": json.loads(row["metadata"]),
                }

    def health_check(self) -> dict[str, Any]:
        """Check backend health."""
        base_status = super().health_check()
        if base_status["status"] == "healthy":
            base_status["backend_type"] = "numpy"
            base_status["embedding_type"] = "deterministic_hash"
        return cast("dict[str, Any]", base_status)
