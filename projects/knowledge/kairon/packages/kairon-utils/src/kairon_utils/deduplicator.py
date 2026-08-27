"""
Content Deduplication.

Prevent duplicate content using SHA256 hashing.
Extracted from D_Harvest utils/deduplicator.py.
"""

import hashlib
import json
import logging
from pathlib import Path

_log = logging.getLogger(__name__)


class ContentDeduplicator:
    """Prevent duplicate content via SHA256 hash tracking."""

    def __init__(self, cache_dir: Path | None = None) -> None:
        self.cache_dir = cache_dir or Path(".omc/deduplication")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._seen_hashes: set[str] = set()
        self._load_cache()

    def _load_cache(self) -> None:
        """Load seen content hashes from disk."""
        cache_file = self.cache_dir / "seen_hashes.json"
        if cache_file.exists():
            try:
                with open(cache_file) as f:
                    self._seen_hashes = set(json.load(f))
                _log.info(f"Loaded {len(self._seen_hashes)} seen hashes from cache")
            except (OSError, json.JSONDecodeError) as e:
                _log.warning(f"Failed to load deduplication cache: {e}")
                self._seen_hashes = set()

    def _save_cache(self) -> None:
        """Persist seen hashes to disk."""
        cache_file = self.cache_dir / "seen_hashes.json"
        try:
            with open(cache_file, "w") as f:
                json.dump(list(self._seen_hashes), f)
        except OSError as e:
            _log.error(f"Failed to save deduplication cache: {e}")

    def compute_content_hash(self, content: str) -> str:
        """
        Compute SHA256 hash of content.

        Args:
            content: Content to hash.

        Returns:
            SHA256 hash as hexadecimal string.
        """
        return hashlib.sha256(content.encode("utf-8"), usedforsecurity=False).hexdigest()

    async def is_duplicate(self, content: str, source_id: str) -> bool:
        """
        Check if content has been seen before.

        Args:
            content: Content to check.
            source_id: Source identifier.

        Returns:
            True if duplicate, False if new content.
        """
        content_hash = self.compute_content_hash(content)
        composite_key = f"{source_id}:{content_hash}"

        if composite_key in self._seen_hashes:
            _log.info(f"Duplicate content detected for {source_id} (hash: {content_hash[:16]}...)")
            return True

        self._seen_hashes.add(composite_key)
        self._save_cache()
        return False

    async def mark_seen(self, content: str, source_id: str) -> None:
        """
        Mark content as seen.

        Args:
            content: Content to mark.
            source_id: Source identifier.
        """
        await self.is_duplicate(content, source_id)

    def get_stats(self) -> dict:
        """
        Get deduplication statistics.

        Returns:
            Dictionary with stats.
        """
        return {"total_seen": len(self._seen_hashes), "cache_dir": str(self.cache_dir)}

    def clear_cache(self, older_than_days: int = 30) -> None:
        """
        Clear all entries from cache.

        Args:
            older_than_days: Not used in current implementation (clears all).
        """
        self._seen_hashes.clear()
        self._save_cache()
        _log.info("Deduplication cache cleared")
