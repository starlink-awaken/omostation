"""File-level write lock mechanism for high-frequency files.

Provides atomic lock acquisition with timeout, conflict detection via file hash,
and lock state monitoring. Designed for multi-agent concurrent write scenarios.

Lock files are stored as YAML in the locks/ directory with the pattern:
    locks/<sanitized_path>.lock.yaml

Each lock contains:
    - run_id: workflow run identifier
    - actor: agent/process holding the lock
    - scope: file path being locked
    - created_at: ISO-8601 timestamp
    - last_heartbeat: ISO-8601 timestamp (for liveness)
    - expires_at: ISO-8601 timestamp (auto-expiry)
    - file_hash: SHA-256 of file content at lock time (conflict detection)
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import yaml

WORKSPACE = Path(__file__).resolve().parents[1]
LOCKS_DIR = WORKSPACE / "locks"

# Default lock timeout: 30 minutes
DEFAULT_TIMEOUT_S = 1800
# Heartbeat interval: 60 seconds
HEARTBEAT_INTERVAL_S = 60
# Deadlock detection threshold: 5 minutes without heartbeat
DEADLOCK_THRESHOLD_S = 300


@dataclass
class FileLock:
    """Represents a file-level write lock."""

    run_id: str
    actor: str
    scope: str
    created_at: str = ""
    last_heartbeat: str = ""
    expires_at: str = ""
    file_hash: str = ""

    def __post_init__(self) -> None:
        now = datetime.now(timezone.utc).isoformat()
        if not self.created_at:
            self.created_at = now
        if not self.last_heartbeat:
            self.last_heartbeat = now
        if not self.expires_at:
            self.expires_at = datetime.now(timezone.utc).timestamp() + DEFAULT_TIMEOUT_S
            self.expires_at = datetime.fromtimestamp(float(self.expires_at), tz=timezone.utc).isoformat()

    def is_expired(self) -> bool:
        """Check if lock has expired."""
        try:
            exp = datetime.fromisoformat(self.expires_at)
            return datetime.now(timezone.utc) > exp
        except (ValueError, TypeError):
            return True

    def is_dead(self, threshold_s: float = DEADLOCK_THRESHOLD_S) -> bool:
        """Check if lock holder appears dead (no heartbeat)."""
        try:
            hb = datetime.fromisoformat(self.last_heartbeat)
            elapsed = (datetime.now(timezone.utc) - hb).total_seconds()
            return elapsed > threshold_s
        except (ValueError, TypeError):
            return True

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for YAML output."""
        return asdict(self)


def _lock_path(file_path: str | Path) -> Path:
    """Derive lock file path from target file path.

    Sanitizes path separators and special characters for filesystem safety.
    """
    rel = str(file_path).replace(os.sep, "_").replace("/", "_")
    # Remove leading dots and sanitize
    rel = rel.lstrip(".").strip("_")
    if not rel:
        rel = "root"
    return LOCKS_DIR / f"{rel}.lock.yaml"


def _file_hash(file_path: str | Path) -> str:
    """Compute SHA-256 hash of file content. Returns empty string if file missing."""
    p = Path(file_path)
    if not p.is_file():
        return ""
    try:
        h = hashlib.sha256()
        with open(p, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return ""


def acquire_lock(
    file_path: str | Path,
    run_id: str,
    actor: str,
    timeout_s: int = DEFAULT_TIMEOUT_S,
    force: bool = False,
) -> FileLock | None:
    """Acquire a write lock on a file.

    Args:
        file_path: Path to the file to lock (relative to workspace or absolute).
        run_id: Workflow run identifier.
        actor: Agent or process requesting the lock.
        timeout_s: Lock timeout in seconds.
        force: If True, break existing expired/dead locks.

    Returns:
        FileLock if acquired, None if file is already locked by another actor.
    """
    abs_path = WORKSPACE / file_path if not Path(file_path).is_absolute() else Path(file_path)
    lock_p = _lock_path(file_path)

    # Check existing lock
    existing = read_lock(file_path)
    if existing is not None:
        if existing.run_id == run_id:
            # Same run re-acquiring: update heartbeat
            existing.last_heartbeat = datetime.now(timezone.utc).isoformat()
            _write_lock_file(lock_p, existing)
            return existing
        if existing.is_expired() or existing.is_dead() or force:
            # Stale lock: break it
            pass
        else:
            # Active lock by another actor
            return None

    # Compute file hash for conflict detection
    fhash = _file_hash(abs_path)

    lock = FileLock(
        run_id=run_id,
        actor=actor,
        scope=str(file_path),
        file_hash=fhash,
    )
    # Override timeout
    lock.expires_at = datetime.now(timezone.utc).timestamp() + timeout_s
    lock.expires_at = datetime.fromtimestamp(float(lock.expires_at), tz=timezone.utc).isoformat()

    _write_lock_file(lock_p, lock)
    return lock


def release_lock(file_path: str | Path, run_id: str) -> bool:
    """Release a file lock.

    Args:
        file_path: Path to the locked file.
        run_id: Must match the lock's run_id for safety.

    Returns:
        True if lock was released, False if not found or run_id mismatch.
    """
    lock_p = _lock_path(file_path)
    if not lock_p.is_file():
        return False

    existing = read_lock(file_path)
    if existing is None:
        return False
    if existing.run_id != run_id:
        return False

    try:
        lock_p.unlink()
        return True
    except OSError:
        return False


def read_lock(file_path: str | Path) -> FileLock | None:
    """Read the current lock for a file.

    Returns:
        FileLock if locked, None if no lock exists.
    """
    lock_p = _lock_path(file_path)
    if not lock_p.is_file():
        return None
    try:
        data = yaml.safe_load(lock_p.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return None
        return FileLock(
            run_id=str(data.get("run_id", "")),
            actor=str(data.get("actor", "")),
            scope=str(data.get("scope", "")),
            created_at=str(data.get("created_at", "")),
            last_heartbeat=str(data.get("last_heartbeat", "")),
            expires_at=str(data.get("expires_at", "")),
            file_hash=str(data.get("file_hash", "")),
        )
    except Exception:
        return None


def heartbeat(file_path: str | Path, run_id: str) -> bool:
    """Update heartbeat for an active lock.

    Returns:
        True if heartbeat updated, False if lock not found or run_id mismatch.
    """
    lock_p = _lock_path(file_path)
    existing = read_lock(file_path)
    if existing is None or existing.run_id != run_id:
        return False

    existing.last_heartbeat = datetime.now(timezone.utc).isoformat()
    _write_lock_file(lock_p, existing)
    return True


def check_conflict(file_path: str | Path) -> dict[str, Any] | None:
    """Check if a file has been modified since it was locked.

    Returns:
        Dict with conflict details if hash mismatch, None if no conflict.
    """
    existing = read_lock(file_path)
    if existing is None:
        return None

    abs_path = WORKSPACE / file_path if not Path(file_path).is_absolute() else Path(file_path)
    current_hash = _file_hash(abs_path)

    if not existing.file_hash or not current_hash:
        return None

    if existing.file_hash != current_hash:
        return {
            "file": str(file_path),
            "locked_hash": existing.file_hash,
            "current_hash": current_hash,
            "locked_by": existing.actor,
            "run_id": existing.run_id,
            "locked_at": existing.created_at,
        }
    return None


def list_locks() -> list[FileLock]:
    """List all active locks in the locks directory."""
    locks: list[FileLock] = []
    if not LOCKS_DIR.is_dir():
        return locks
    for lock_file in sorted(LOCKS_DIR.glob("*.lock.yaml")):
        lock = read_lock(lock_file.stem.replace(".lock", ""))
        if lock is not None:
            locks.append(lock)
    return locks


def list_expired_locks() -> list[FileLock]:
    """List all expired locks."""
    return [l for l in list_locks() if l.is_expired()]


def list_dead_locks(threshold_s: float = DEADLOCK_THRESHOLD_S) -> list[FileLock]:
    """List all dead locks (no heartbeat within threshold)."""
    return [l for l in list_locks() if l.is_dead(threshold_s)]


def cleanup_expired() -> list[str]:
    """Remove all expired locks. Returns list of cleaned file paths."""
    cleaned: list[str] = []
    for lock in list_expired_locks():
        lock_p = _lock_path(lock.scope)
        try:
            lock_p.unlink()
            cleaned.append(lock.scope)
        except OSError:
            pass
    return cleaned


def detect_deadlocks() -> list[dict[str, Any]]:
    """Detect potential deadlocks (dead locks with active files).

    Returns list of deadlock reports.
    """
    deadlocks: list[dict[str, Any]] = []
    for lock in list_dead_locks():
        abs_path = WORKSPACE / lock.scope
        deadlocks.append(
            {
                "file": lock.scope,
                "run_id": lock.run_id,
                "actor": lock.actor,
                "locked_at": lock.created_at,
                "last_heartbeat": lock.last_heartbeat,
                "file_exists": abs_path.is_file(),
            }
        )
    return deadlocks


def monitor_high_frequency(files: list[str | Path]) -> list[dict[str, Any]]:
    """Monitor a list of high-frequency files for lock contention.

    Returns list of contention reports.
    """
    reports: list[dict[str, Any]] = []
    for f in files:
        lock = read_lock(f)
        conflict = check_conflict(f)
        report: dict[str, Any] = {
            "file": str(f),
            "locked": lock is not None,
            "conflict": conflict is not None,
        }
        if lock is not None:
            report["lock"] = lock.to_dict()
            report["expired"] = lock.is_expired()
            report["dead"] = lock.is_dead()
        if conflict is not None:
            report["conflict_detail"] = conflict
        reports.append(report)
    return reports


def _write_lock_file(path: Path, lock: FileLock) -> None:
    """Write lock data to YAML file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    data = lock.to_dict()
    # Convert datetime objects to strings for YAML serialization
    for k, v in data.items():
        if isinstance(v, datetime):
            data[k] = v.isoformat()
    path.write_text(
        yaml.dump(data, default_flow_style=False, allow_unicode=True),
        encoding="utf-8",
    )


# --- CLI entry point ---


def main() -> int:
    """CLI interface for file lock operations."""
    import argparse

    parser = argparse.ArgumentParser(description="File lock management")
    sub = parser.add_subparsers(dest="command")

    # acquire
    p_acquire = sub.add_parser("acquire", help="Acquire a file lock")
    p_acquire.add_argument("file", help="File path to lock")
    p_acquire.add_argument("--run-id", required=True, help="Run identifier")
    p_acquire.add_argument("--actor", required=True, help="Actor name")
    p_acquire.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_S)
    p_acquire.add_argument("--force", action="store_true")

    # release
    p_release = sub.add_parser("release", help="Release a file lock")
    p_release.add_argument("file", help="File path to unlock")
    p_release.add_argument("--run-id", required=True, help="Run identifier")

    # status
    p_status = sub.add_parser("status", help="Check lock status")
    p_status.add_argument("file", nargs="?", help="File path (or all if omitted)")

    # cleanup
    sub.add_parser("cleanup", help="Remove expired locks")

    # deadlocks
    sub.add_parser("deadlocks", help="Detect deadlocks")

    args = parser.parse_args()

    if args.command == "acquire":
        lock = acquire_lock(args.file, args.run_id, args.actor, args.timeout, args.force)
        if lock:
            print(json.dumps(lock.to_dict(), indent=2, default=str))
            return 0
        print(json.dumps({"error": "file_locked", "file": args.file}))
        return 1

    elif args.command == "release":
        ok = release_lock(args.file, args.run_id)
        print(json.dumps({"released": ok, "file": args.file}))
        return 0 if ok else 1

    elif args.command == "status":
        if args.file:
            lock = read_lock(args.file)
            conflict = check_conflict(args.file)
            print(
                json.dumps(
                    {
                        "file": args.file,
                        "lock": lock.to_dict() if lock else None,
                        "conflict": conflict,
                    },
                    indent=2,
                    default=str,
                )
            )
        else:
            locks = list_locks()
            print(json.dumps([l.to_dict() for l in locks], indent=2, default=str))
        return 0

    elif args.command == "cleanup":
        cleaned = cleanup_expired()
        print(json.dumps({"cleaned": cleaned, "count": len(cleaned)}, indent=2))
        return 0

    elif args.command == "deadlocks":
        deadlocks = detect_deadlocks()
        print(json.dumps(deadlocks, indent=2, default=str))
        return 1 if deadlocks else 0

    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
