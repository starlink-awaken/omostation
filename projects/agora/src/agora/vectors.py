"""Vector store abstraction for semantic search.

Provides a simple interface for storing and searching agent messages
by semantic similarity. Adapted from agentmesh gateway core/vector-store.ts.
"""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


class VectorStore:
    """In-memory vector store with simple embedding interface.

    In production, swap the store implementation for a real vector DB
    (e.g. ChromaDB, Qdrant) by providing a different embedder/search backend.
    The public interface mirrors the TypeScript VectorStore class.
    """

    def __init__(self, base_dir: str = "./data/vector-db") -> None:
        self._base_dir = base_dir
        self._collection_name = "agent-context"
        self._initialized = False
        self._documents: dict[str, dict[str, Any]] = {}
        self._embedding_fn = self._simple_tokenize

    def configure(self, base_dir: str) -> None:
        """Update storage directory."""
        self._base_dir = base_dir

    async def initialize(self) -> None:
        """Initialize the vector store."""
        if self._initialized:
            return
        # In-memory store — always ready. Real backends would connect here.
        self._initialized = True
        logger.info("[VectorStore] Initialized (in-memory mode)")

    async def add_message(self, space_id: str, message: dict[str, Any]) -> None:
        """Add an agent message to the store."""
        if not self._initialized:
            logger.warning("[VectorStore] Not initialized, skipping add")
            return

        doc_id = f"{space_id}_{message.get('id', '')}"
        text = self._message_to_text(message)
        self._documents[doc_id] = {
            "id": doc_id,
            "content": text,
            "space_id": space_id,
            "message_id": message.get("id", ""),
            "timestamp": message.get("timestamp", 0),
            "source": message.get("source", "unknown"),
            "type": message.get("type", "event"),
            "_embedding": self._embedding_fn(text),
        }

    async def search_similar(
        self, space_id: str, query: str, limit: int = 5
    ) -> list[dict[str, Any]]:
        """Search for semantically similar messages."""
        if not self._initialized:
            logger.warning("[VectorStore] Not initialized, returning empty")
            return []

        query_emb = self._embedding_fn(query)
        candidates = [
            (doc_id, doc)
            for doc_id, doc in self._documents.items()
            if doc.get("space_id") == space_id
        ]
        if not candidates:
            return []

        scored = [
            (self._cosine_sim(query_emb, doc["_embedding"]), doc)
            for _, doc in candidates
        ]
        scored.sort(key=lambda x: x[0], reverse=True)

        return [
            {
                "id": doc.get("message_id", doc.get("id", "")),
                "type": "event",
                "source": doc.get("source", "unknown"),
                "target": "search",
                "correlation_id": "",
                "timestamp": doc.get("timestamp", 0),
                "payload": {"task": doc.get("content", "")},
            }
            for _, doc in scored[:limit]
        ]

    async def get_count(self, space_id: str) -> int:
        """Get number of documents for a space."""
        if not self._initialized:
            return 0
        return sum(
            1 for doc in self._documents.values() if doc.get("space_id") == space_id
        )

    async def delete_space(self, space_id: str) -> None:
        """Delete all documents for a space."""
        if not self._initialized:
            return
        keys = [
            k for k, v in self._documents.items() if v.get("space_id") == space_id
        ]
        for k in keys:
            self._documents.pop(k, None)

    def is_available(self) -> bool:
        """Check if initialized."""
        return self._initialized

    # -- Private helpers --

    def _message_to_text(self, message: dict[str, Any]) -> str:
        parts: list[str] = []
        payload = message.get("payload") or {}
        if payload.get("task"):
            parts.append(f"Task: {payload['task']}")
        if message.get("result"):
            parts.append(f"Result: {json.dumps(message['result'], default=str)}")
        if message.get("error"):
            err = message["error"]
            parts.append(f"Error: {err if isinstance(err, str) else err.get('message', '')}")
        return "\n".join(parts) or json.dumps(message, default=str)

    @staticmethod
    def _simple_tokenize(text: str) -> list[float]:
        """Simple bag-of-words embedding for demo/in-memory use.

        Replace with real embeddings (e.g. sentence-transformers) in production.
        """
        import hashlib

        words = text.lower().split()
        vec = [0.0] * 64
        for word in words:
            h = int(hashlib.sha256(word.encode()).hexdigest()[:8], 16)
            idx = h % 64
            vec[idx] += 1.0
        norm = sum(x * x for x in vec) ** 0.5
        return [x / norm for x in vec] if norm else vec

    @staticmethod
    def _cosine_sim(a: list[float], b: list[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b))
        return dot  # already normalized


# Global singleton
vector_store = VectorStore()
