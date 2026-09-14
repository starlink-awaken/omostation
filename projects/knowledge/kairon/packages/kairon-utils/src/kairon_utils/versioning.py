from __future__ import annotations

"""
Content Versioning System.

Track content evolution over time with audit trail and SHA256 hashing.
Extracted from D_Harvest utils/versioning.py.

B-1 P0 跨仓 SSOT 接入: `_append_version_log` 改用 AppendOnlyLog + fcntl_lock
(R48 探路结论 — 跨进程并发写存在丢行风险, P0 修复).
"""

import hashlib
import json
import logging
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from kairon_utils.append_only_log import AppendOnlyLog, fcntl_lock

_log = logging.getLogger(__name__)


@dataclass
class ContentVersion:
    """Track content version history."""

    content_hash: str
    previous_hash: str | None
    version_number: int
    source_id: str
    harvested_at: str
    content_size: int
    metadata: dict

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> ContentVersion:
        """Create from dictionary."""
        return cls(**data)


class ContentVersionTracker:
    """Track content evolution over time."""

    def __init__(self, storage_dir: Path | None = None) -> None:
        self.storage_dir = storage_dir or Path(".omc/versioning")
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def _get_version_file(self, source_id: str) -> Path:
        """Get version storage file for source."""
        return self.storage_dir / f"{source_id}_versions.jsonl"

    def compute_content_hash(self, content: str) -> str:
        """
        Compute SHA256 hash of content.

        Args:
            content: Content to hash.

        Returns:
            SHA256 hash as hexadecimal string.
        """
        return hashlib.sha256(content.encode("utf-8"), usedforsecurity=False).hexdigest()

    async def record_version(self, source_id: str, content: str, metadata: dict | None = None) -> ContentVersion:
        """
        Record new version of content.

        Args:
            source_id: Source identifier.
            content: Content data.
            metadata: Optional metadata to attach.

        Returns:
            ContentVersion record.
        """
        content_hash = self.compute_content_hash(content)

        previous_version = await self.get_latest_version(source_id)
        previous_hash = previous_version.content_hash if previous_version else None
        version_number = (previous_version.version_number + 1) if previous_version else 1

        version = ContentVersion(
            content_hash=content_hash,
            previous_hash=previous_hash,
            version_number=version_number,
            source_id=source_id,
            harvested_at=datetime.now(UTC).isoformat(),
            content_size=len(content),
            metadata=metadata or {},
        )

        await self._append_version_log(version)

        _log.info(f"Recorded version {version_number} for {source_id} (hash: {content_hash[:16]}...)")

        return version

    async def get_latest_version(self, source_id: str) -> ContentVersion | None:
        """
        Get latest version of content.

        Args:
            source_id: Source identifier.

        Returns:
            Latest ContentVersion or None.
        """
        version_file = self._get_version_file(source_id)

        if not version_file.exists():
            return None

        try:
            with open(version_file) as f:
                lines = f.readlines()
                if lines:
                    return ContentVersion.from_dict(json.loads(lines[-1]))
        except (OSError, json.JSONDecodeError) as e:
            _log.error(f"Failed to read version file for {source_id}: {e}")

        return None

    async def get_version_history(self, source_id: str, limit: int = 10) -> list[ContentVersion]:
        """
        Get version history for source.

        Args:
            source_id: Source identifier.
            limit: Maximum number of versions to return.

        Returns:
            List of ContentVersion (newest first).
        """
        version_file = self._get_version_file(source_id)

        if not version_file.exists():
            return []

        versions = []
        try:
            with open(version_file) as f:
                lines = f.readlines()
                for line in reversed(lines[-limit:]):
                    versions.append(ContentVersion.from_dict(json.loads(line)))
        except (OSError, json.JSONDecodeError) as e:
            _log.error(f"Failed to read version history for {source_id}: {e}")

        return versions

    async def _append_version_log(self, version: ContentVersion) -> None:
        """
        Append version entry to log file (B-1 + E3 P0: AppendOnlyLog + fcntl_lock + asyncio.to_thread).

        从裸 `open(..., "a")` 升级:
          - AppendOnlyLog.sort_keys=True 保 SSOT 跨仓顺序确定性
          - fcntl.flock 跨进程安全 (旧版无锁, 跨进程并发会丢行)
          - asyncio.to_thread 包装 fcntl 同步锁 → event loop 不阻塞 (E3 P0)

        Args:
            version: ContentVersion to append.
        """
        import asyncio

        version_file = self._get_version_file(version.source_id)
        lock_file = version_file.with_suffix(".lock")

        def _do_append() -> None:
            log = AppendOnlyLog(version_file, lock=fcntl_lock(lock_file))
            log.append(version.to_dict())

        try:
            await asyncio.to_thread(_do_append)
        except OSError as e:
            _log.error(f"Failed to write version log for {version.source_id}: {e}")

    async def compare_versions(self, source_id: str, hash1: str, hash2: str) -> dict:
        """
        Compare two content versions and return diff summary.

        Args:
            source_id: Source identifier.
            hash1: First content hash.
            hash2: Second content hash.

        Returns:
            Dictionary with comparison results.
        """
        versions = await self.get_version_history(source_id, limit=100)

        v1 = next((v for v in versions if v.content_hash == hash1), None)
        v2 = next((v for v in versions if v.content_hash == hash2), None)

        if not v1 or not v2:
            return {"status": "not_found", "message": "One or both versions not found"}

        return {
            "status": "compared",
            "version1": v1.version_number,
            "version2": v2.version_number,
            "size_delta": v2.content_size - v1.content_size,
            "time_delta": (
                datetime.fromisoformat(v2.harvested_at) - datetime.fromisoformat(v1.harvested_at)
            ).total_seconds(),
        }

    def get_statistics(self) -> dict:
        """
        Get overall versioning statistics.

        Returns:
            Dictionary with stats.
        """
        total_versions = 0
        source_counts = {}

        for version_file in self.storage_dir.glob("*_versions.jsonl"):
            try:
                with open(version_file) as f:
                    lines = f.readlines()
                    count = len(lines)
                    source_id = version_file.stem.replace("_versions.jsonl", "")
                    source_counts[source_id] = count
                    total_versions += count
            except (OSError, json.JSONDecodeError):
                pass

        return {
            "total_sources": len(source_counts),
            "total_versions": total_versions,
            "sources": source_counts,
        }
