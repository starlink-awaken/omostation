"""Tool embedding management — storage and semantic search."""

import struct
import threading

import structlog

logger = structlog.get_logger(__name__)

_EMBEDDING_DIM = 384  # all-MiniLM-L6-v2 dimension


class EmbeddingCache:
    """Thread-safe in-memory embedding cache with vectorized cosine similarity."""

    def __init__(self, capacity: int = 5000):
        self._lock = threading.Lock()
        self._capacity = capacity
        self._tool_ids: list[str] = []
        self._embeddings: np.ndarray | None = None  # noqa: F821

    def load(self, tool_ids: list[str], embeddings: "np.ndarray") -> None:  # noqa: F821
        """Replace cache contents with a new set of embeddings."""
        import numpy as np

        with self._lock:
            self._tool_ids = tool_ids
            self._embeddings = np.array(embeddings, dtype=np.float32)

    def search(self, query_embedding: "np.ndarray", top_k: int = 10) -> list[tuple[str, float]]:  # noqa: F821
        """Return top-k (tool_id, score) pairs via vectorized cosine similarity."""
        if self._embeddings is None or len(self._tool_ids) == 0:
            return []
        import numpy as np

        scores = self._embeddings @ query_embedding  # vectorized dot product
        top_indices = np.argsort(scores)[-top_k:][::-1]
        return [(self._tool_ids[i], float(scores[i])) for i in top_indices]

    @property
    def loaded(self) -> bool:
        """Whether the cache contains data."""
        return self._embeddings is not None and len(self._tool_ids) > 0

    @property
    def size(self) -> int:
        """Number of embeddings currently cached."""
        return len(self._tool_ids) if self._embeddings is not None else 0

    def clear(self) -> None:
        """Evict all cached embeddings."""
        with self._lock:
            self._tool_ids = []
            self._embeddings = None


class EmbeddingStore:
    """Store and search tool embeddings using SQLite + in-memory cache + optional sentence-transformers."""

    def __init__(self, db_path: str, auto_refresh: bool = True):
        self._db_path = db_path
        self._conn = None
        self._model = None  # Lazy-loaded model or False sentinel
        self._cache = EmbeddingCache()
        self._dirty = True
        self._auto_refresh = auto_refresh
        self._ensure_schema()

    def _get_conn(self):
        if self._conn is None:
            import sqlite3

            self._conn = sqlite3.connect(self._db_path)
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def _ensure_schema(self):
        conn = self._get_conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tool_embeddings (
                tool_id TEXT PRIMARY KEY,
                embedding BLOB,
                updated_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.commit()

    def _get_model(self):
        """Lazy-load sentence-transformers model (cached)."""
        if self._model is not None:
            return self._model if self._model is not False else None
        try:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer("all-MiniLM-L6-v2")
            logger.info("embedding_model_loaded", model="all-MiniLM-L6-v2")
        except Exception as e:
            logger.warning("embedding_model_unavailable", error=str(e))
            self._model = False  # Sentinel: don't retry
        return self._model if self._model is not False else None

    @property
    def available(self) -> bool:
        """Check if embedding model is available."""
        return self._get_model() is not None

    def compute_embedding(self, text: str) -> list[float] | None:
        """Compute embedding vector for text. Returns None if model unavailable."""
        model = self._get_model()
        if not model:
            return None
        try:
            emb = model.encode(text, normalize_embeddings=True)
            return [float(v) for v in emb]
        except Exception as e:
            logger.warning("embedding_failed", error=str(e))
            return None

    def refresh_cache(self) -> None:
        """Load all embeddings from SQLite into in-memory cache."""
        import numpy as np

        conn = self._get_conn()
        rows = conn.execute("SELECT tool_id, embedding FROM tool_embeddings").fetchall()
        if not rows:
            self._cache.clear()
            self._dirty = False
            return
        tool_ids: list[str] = []
        embeddings: list[np.ndarray] = []
        for row in rows:
            blob = row["embedding"]
            if not blob:
                continue
            try:
                emb = np.frombuffer(blob, dtype=np.float32)
                if len(emb) != _EMBEDDING_DIM:
                    continue
                tool_ids.append(row["tool_id"])
                embeddings.append(emb)
            except Exception:  # noqa: S112
                continue
        if embeddings:
            self._cache.load(tool_ids, np.array(embeddings, dtype=np.float32))
        else:
            self._cache.clear()
        self._dirty = False

    def save_embedding(self, tool_id: str, embedding: list[float]) -> bool:
        """Save embedding vector to database. embedding should be 384-dim float list."""
        try:
            data = struct.pack(f"{len(embedding)}f", *embedding)
            conn = self._get_conn()
            conn.execute(
                """
                INSERT INTO tool_embeddings (tool_id, embedding, updated_at)
                VALUES (?, ?, datetime('now'))
                ON CONFLICT(tool_id) DO UPDATE SET
                    embedding=excluded.embedding,
                    updated_at=excluded.updated_at
            """,
                (tool_id, data),
            )
            conn.commit()
            self._dirty = True  # Invalidate cache
            return True
        except Exception as e:
            logger.warning("save_embedding_failed", tool_id=tool_id, error=str(e))
            return False

    def save_text_embedding(self, tool_id: str, text: str) -> bool:
        """Compute and save embedding for text in one call."""
        emb = self.compute_embedding(text)
        if emb is None:
            return False
        return self.save_embedding(tool_id, emb)

    def search_similar(self, query: str, top_k: int = 10) -> list[tuple[str, float]]:
        """Search tools by embedding similarity.
        Uses in-memory cache for fast vector similarity after initial load.
        Returns [(tool_id, cosine_similarity)] sorted by similarity descending.
        Returns empty list if embeddings are unavailable.
        """
        query_vec = self.compute_embedding(query)
        if query_vec is None:
            return []

        import numpy as np

        query_np = np.array(query_vec, dtype=np.float32)

        # Auto-refresh cache if dirty or empty
        if self._dirty or not self._cache.loaded:
            if self._auto_refresh:
                self.refresh_cache()

        return self._cache.search(query_np, top_k=top_k)

    def rebuild_all(self, catalog) -> int:
        """Rebuild embeddings for all tools in catalog. Returns count."""
        tools = catalog.list_tools()
        count = 0
        for t in tools:
            text = f"{t.get('name', '')} {t.get('description', '')} {' '.join(t.get('tags', []))}"
            if self.save_text_embedding(t["id"], text):
                count += 1
        logger.info("embeddings_rebuilt", total=len(tools), saved=count)
        return count

    @property
    def stats(self) -> dict:
        """Return cache and database statistics."""
        conn = self._get_conn()
        try:
            total_in_db = conn.execute("SELECT COUNT(*) as cnt FROM tool_embeddings").fetchone()["cnt"]
        except Exception:
            total_in_db = 0
        return {
            "cache_loaded": self._cache.loaded,
            "cache_size": self._cache.size,
            "total_embeddings": total_in_db,
            "dirty": self._dirty,
        }

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None
        self._cache.clear()
