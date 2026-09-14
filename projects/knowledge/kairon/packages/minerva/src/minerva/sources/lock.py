from __future__ import annotations

"""
---
Type: Module
Status: ACTIVE
Version: 1.0.0
Authority: nucleus/Z-Core/L0-Genome/R0-ACT-SYS-AX01-10_holographic_metadata_axiom.md
Layer: L3
---
"""
# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Lock ≡ Module
# 内涵 ≝ {Lock}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, Lock)}
# 功能 ⊢ {Init_Lock, Execute_Lock, Validate_Lock}
# =============================================================================

# ---
# domain: D-Harvest
# layer: organ
# status: active
# ---

"""
Source-level locking to prevent concurrent harvests

Implements distributed locking mechanism to ensure only one harvest
operation can run per source at a time. Uses file-based locking with
automatic timeout and cleanup.
"""
import logging
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

_log = logging.getLogger(__name__)


@dataclass
class LockResult:
    """Lock acquisition result"""

    acquired: bool
    lock_id: str | None = None
    error: str | None = None


class SourceLock:
    """
    File-based lock for preventing concurrent harvests of same source

    Lock files stored in: .omc/locks/sources/{source_id}.lock
    Each lock contains metadata about the holder and timestamp.
    """

    def __init__(self, lock_dir: Path | None = None, timeout_seconds: int = 3600) -> None:
        """
        Initialize lock manager

        Args:
            lock_dir: Directory for lock files (default: .omc/locks/sources/)
            timeout_seconds: Maximum lock lifetime before auto-release (default: 1 hour)
        """
        self.lock_dir = lock_dir or Path(".omc/locks/sources")
        self.timeout_seconds = timeout_seconds
        self._ensure_lock_dir()

    def _ensure_lock_dir(self) -> None:
        """Create lock directory if it doesn't exist"""
        self.lock_dir.mkdir(parents=True, exist_ok=True)

    def _get_lock_path(self, source_id: str) -> Path:
        """Get lock file path for a source"""
        return self.lock_dir / f"{source_id}.lock"

    def _is_lock_stale(self, lock_path: Path) -> bool:
        """
        Check if a lock has exceeded its timeout

        Args:
            lock_path: Path to lock file

        Returns:
            True if lock is stale and should be broken
        """
        try:
            mtime = lock_path.stat().st_mtime
            age_seconds = datetime.now(UTC).timestamp() - mtime
            return age_seconds > self.timeout_seconds
        except OSError:
            return False

    async def acquire(self, source_id: str, holder_id: str) -> LockResult:
        """
        Attempt to acquire lock for a source

        Args:
            source_id: Unique source identifier
            holder_id: Identifier for lock holder (e.g., process ID, worker name)

        Returns:
            LockResult with acquisition status
        """
        lock_path = self._get_lock_path(source_id)

        try:
            # Try to create lock file exclusively
            fd = os.open(lock_path, os.O_CREAT | os.O_WRONLY | os.O_EXCL)

            try:
                # Write lock metadata
                lock_data = {
                    "source_id": source_id,
                    "holder_id": holder_id,
                    "acquired_at": datetime.now(UTC).isoformat(),
                }

                with os.fdopen(fd, "w") as f:
                    import json

                    json.dump(lock_data, f)
                    f.flush()
                    os.fsync(f.fileno())

                _log.info(f"Lock acquired for source {source_id} by {holder_id}")
                return LockResult(acquired=True, lock_id=f"{source_id}:{holder_id}")

            except OSError:
                os.close(fd)
                raise

        except FileExistsError:
            # Lock file exists - check if stale
            if self._is_lock_stale(lock_path):
                _log.warning(f"Breaking stale lock for source {source_id}")
                try:
                    lock_path.unlink()
                    # Retry acquisition after breaking stale lock
                    return await self.acquire(source_id, holder_id)
                except OSError:
                    pass

            # Read lock holder for error message
            try:
                with open(lock_path) as f:
                    import json

                    lock_data = json.load(f)
                    holder = lock_data.get("holder_id", "unknown")
                return LockResult(acquired=False, error=f"Source {source_id} is locked by {holder}")
            except (OSError, json.JSONDecodeError):  # type: ignore[reportPossiblyUnboundVariable]
                return LockResult(acquired=False, error=f"Source {source_id} is locked")

        except OSError as e:
            return LockResult(acquired=False, error=f"Failed to acquire lock: {e}")

    async def release(self, source_id: str, holder_id: str) -> bool:
        """
        Release lock for a source

        Args:
            source_id: Unique source identifier
            holder_id: Identifier for lock holder (must match acquirer)

        Returns:
            True if lock was released, False otherwise
        """
        lock_path = self._get_lock_path(source_id)

        try:
            # Verify holder matches before releasing
            with open(lock_path) as f:
                import json

                lock_data = json.load(f)
                if lock_data.get("holder_id") != holder_id:
                    _log.warning(
                        f"Attempted to release lock for {source_id} "
                        f"by non-holder {holder_id} (actual: {lock_data.get('holder_id')})"
                    )
                    return False

            lock_path.unlink()
            _log.info(f"Lock released for source {source_id} by {holder_id}")
            return True

        except FileNotFoundError:
            _log.warning(f"Lock file not found for source {source_id}")
            return False
        except (OSError, json.JSONDecodeError) as e:  # type: ignore[reportPossiblyUnboundVariable]
            _log.error(f"Failed to release lock for {source_id}: {e}")
            return False

    async def is_locked(self, source_id: str) -> bool:
        """
        Check if a source is currently locked

        Args:
            source_id: Unique source identifier

        Returns:
            True if source is locked (and lock is not stale)
        """
        lock_path = self._get_lock_path(source_id)

        if not lock_path.exists():
            return False

        # Check if lock is stale
        if self._is_lock_stale(lock_path):
            return False

        return True
