from __future__ import annotations

"""
Extracted from SharedBrain D_Harvest → minerva.

---
Type: Module
Status: ACTIVE
Version: 1.0.0
Authority: nucleus/Z-Core/L0-Genome/R0-ACT-SYS-AX01-10_holographic_metadata_axiom.md
Layer: L3
---
"""
# Cache ≡ Module
# 内涵 ≝ {Cache}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, Cache)}
# 功能 ⊢ {Init_Cache, Execute_Cache, Validate_Cache}
# =============================================================================

# ---
# domain: D-Harvest
# layer: organ
# status: active
# ---

"""
Embedding cache layer to reduce API dependence

Caches vector embeddings locally to avoid repeated API calls.
Reduces cost, improves latency, and provides fallback when API unavailable.
"""
import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_log = logging.getLogger(__name__)


@dataclass
class CachedEmbedding:
    """Cached vector embedding"""

    text_hash: str  # SHA256 hash of input text
    embedding: list[float]  # Vector embedding
    model: str  # Model name used
    cached_at: str  # ISO timestamp
    metadata: dict[str, Any] | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization"""
        return {
            "text_hash": self.text_hash,
            "embedding": self.embedding,
            "model": self.model,
            "cached_at": self.cached_at,
            "metadata": self.metadata or {},
        }

    @classmethod
    def from_dict(cls, data: dict) -> CachedEmbedding:
        """Create from dictionary"""
        return cls(**data)


class EmbeddingCache:
    """
    Local cache for vector embeddings

    Reduces API calls and provides offline fallback.
    """

    def __init__(self, cache_dir: Path | None = None, max_size_mb: int = 1000) -> None:
        """
        Initialize embedding cache

        Args:
            cache_dir: Directory for cache files (default: .omc/cache/embeddings/)
            max_size_mb: Maximum cache size in MB
        """
        self.cache_dir = cache_dir or Path(".omc/cache/embeddings")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.max_size_mb = max_size_mb
        self._memory_cache: dict[str, CachedEmbedding] = {}

    def _hash_text(self, text: str) -> str:
        """
        Generate SHA256 hash of text

        Args:
            text: Input text

        Returns:
            Hexadecimal hash string
        """
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def _get_cache_path(self, text_hash: str) -> Path:
        """Get cache file path for a hash"""
        # Use first 2 chars as subdirectory for sharding
        subdir = text_hash[:2]
        return self.cache_dir / subdir / f"{text_hash}.json"

    async def get(self, text: str, model: str) -> list[float] | None:
        """
        Get cached embedding if available

        Args:
            text: Input text
            model: Model name

        Returns:
            Embedding vector if cached, None otherwise
        """
        text_hash = self._hash_text(text)

        # Check memory cache first
        if text_hash in self._memory_cache:
            cached = self._memory_cache[text_hash]
            if cached.model == model:
                _log.debug(f"Cache hit (memory) for {text_hash[:16]}...")
                return cached.embedding

        # Check disk cache
        cache_path = self._get_cache_path(text_hash)

        if not cache_path.exists():
            return None

        try:
            with open(cache_path) as f:
                data = json.load(f)

            cached = CachedEmbedding.from_dict(data)

            if cached.model != model:
                return None

            # Store in memory cache
            self._memory_cache[text_hash] = cached

            _log.debug(f"Cache hit (disk) for {text_hash[:16]}...")
            return cached.embedding

        except (OSError, json.JSONDecodeError) as e:
            _log.error(f"Failed to load cache for {text_hash[:16]}...: {e}")
            return None

    async def set(self, text: str, embedding: list[float], model: str, metadata: dict[str, Any] | None = None) -> bool:
        """
        Cache embedding for text

        Args:
            text: Input text
            embedding: Vector embedding
            model: Model name
            metadata: Optional additional metadata

        Returns:
            True if cached successfully
        """
        text_hash = self._hash_text(text)

        cached = CachedEmbedding(
            text_hash=text_hash,
            embedding=embedding,
            model=model,
            cached_at=datetime.now(UTC).isoformat(),
            metadata=metadata,
        )

        # Store in memory
        self._memory_cache[text_hash] = cached

        # Store on disk
        cache_path = self._get_cache_path(text_hash)

        try:
            cache_path.parent.mkdir(parents=True, exist_ok=True)

            with open(cache_path, "w") as f:
                json.dump(cached.to_dict(), f)

            _log.debug(f"Cached embedding for {text_hash[:16]}...")
            return True

        except (OSError, json.JSONDecodeError) as e:
            _log.error(f"Failed to cache embedding for {text_hash[:16]}...: {e}")
            return False

    async def clear(self, older_than: str | None = None) -> int:
        """
        Clear cached embeddings

        Args:
            older_than: Optional ISO timestamp - only clear entries older than this

        Returns:
            Number of cache entries cleared
        """
        cleared = 0

        # Clear memory cache
        if older_than:
            threshold = datetime.fromisoformat(older_than)
            to_remove = []

            for text_hash, cached in self._memory_cache.items():
                cached_at = datetime.fromisoformat(cached.cached_at)
                if cached_at < threshold:
                    to_remove.append(text_hash)

            for text_hash in to_remove:
                del self._memory_cache[text_hash]
                cleared += 1
        else:
            cleared = len(self._memory_cache)
            self._memory_cache.clear()

        # Clear disk cache
        # For simplicity, clear all if older_than not specified
        if not older_than:
            for cache_file in self.cache_dir.rglob("*.json"):
                try:
                    cache_file.unlink()
                    cleared += 1
                except OSError:
                    pass

        _log.info(f"Cleared {cleared} cache entries")
        return cleared

    async def get_stats(self) -> dict[str, int]:
        """
        Get cache statistics

        Returns:
            Dictionary with cache stats
        """
        # Count disk cache files
        disk_count = 0
        for _ in self.cache_dir.rglob("*.json"):
            disk_count += 1

        return {
            "memory_cache_size": len(self._memory_cache),
            "disk_cache_size": disk_count,
            "total_size": len(self._memory_cache) + disk_count,
        }
