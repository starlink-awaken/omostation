#!/usr/bin/env python3
"""ledger_lock.py — File-based lock for bet-ledger.yaml concurrent access.

Eliminates concurrent modification conflicts on docs/plans/3y-bet-ledger.yaml
by providing advisory file locking with timeout, renewal, and deadlock detection.

Design:
  - Lock file: docs/plans/ledger.lock (same directory as bet-ledger.yaml)
  - Lock acquisition with configurable timeout (default 30s)
  - Lock renewal every 10s (heartbeat to prevent stale locks)
  - Automatic release on process exit (atexit + signal handlers)
  - Lock state monitoring and deadlock detection (>60s held = warning)

Usage:
    from lib.ledger_lock import LedgerLock

    lock = LedgerLock()
    try:
        lock.acquire()
        # ... write operations ...
    finally:
        lock.release()

    # Or as a context manager:
    with LedgerLock():
        # ... write operations ...
"""

from __future__ import annotations

import atexit
import hashlib
import json
import os
import signal
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Lock file lives next to bet-ledger.yaml
WS = Path(__file__).resolve().parents[1]
LOCK_PATH = WS / "docs" / "plans" / "ledger.lock"

# Defaults
DEFAULT_TIMEOUT_S = 30.0
DEFAULT_RENEWAL_INTERVAL_S = 10.0
DEADLOCK_WARNING_S = 60.0
STALE_LOCK_S = 120.0  # Consider lock stale after 2 minutes


@dataclass
class LockInfo:
    """Structured lock state for monitoring."""

    pid: int
    hostname: str
    acquired_at: float
    renewed_at: float
    operation: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps(
            {
                "pid": self.pid,
                "hostname": self.hostname,
                "acquired_at": self.acquired_at,
                "renewed_at": self.renewed_at,
                "operation": self.operation,
                "metadata": self.metadata,
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )

    @classmethod
    def from_json(cls, text: str) -> LockInfo | None:
        try:
            data = json.loads(text)
            return cls(
                pid=int(data["pid"]),
                hostname=str(data["hostname"]),
                acquired_at=float(data["acquired_at"]),
                renewed_at=float(data["renewed_at"]),
                operation=str(data.get("operation", "")),
                metadata=dict(data.get("metadata", {})),
            )
        except (json.JSONDecodeError, KeyError, ValueError, TypeError):
            return None

    def age_seconds(self) -> float:
        return time.time() - self.acquired_at

    def since_renewal(self) -> float:
        return time.time() - self.renewed_at

    def is_process_alive(self) -> bool:
        """Check if the lock-holding process is still running."""
        try:
            os.kill(self.pid, 0)
            return True
        except (OSError, ProcessLookupError):
            return False


class LedgerLockError(RuntimeError):
    """Base exception for lock operations."""


class LockAcquisitionError(LedgerLockError):
    """Raised when lock cannot be acquired within timeout."""


class LockConflictError(LedgerLockError):
    """Raised when another process holds the lock."""


class LedgerLock:
    """File-based advisory lock for bet-ledger.yaml.

    Uses os.open with O_CREAT|O_EXCL for atomic lock creation,
    with fcntl.flock for cross-platform advisory locking (fallback
    to simple file existence on platforms without fcntl).
    """

    def __init__(
        self,
        lock_path: Path | None = None,
        timeout: float = DEFAULT_TIMEOUT_S,
        renewal_interval: float = DEFAULT_RENEWAL_INTERVAL_S,
        operation: str = "",
        metadata: dict[str, Any] | None = None,
    ):
        self._lock_path = lock_path or LOCK_PATH
        self._timeout = timeout
        self._renewal_interval = renewal_interval
        self._operation = operation
        self._metadata = metadata or {}
        self._fd: int | None = None
        self._lock_info: LockInfo | None = None
        self._renewal_thread: _RenewalWorker | None = None
        self._acquired = False
        self._registered_cleanup = False

    @property
    def is_held(self) -> bool:
        return self._acquired and self._fd is not None

    @property
    def lock_info(self) -> LockInfo | None:
        return self._lock_info

    def acquire(self) -> LockInfo:
        """Acquire the lock, blocking until timeout.

        Returns LockInfo on success.
        Raises LockAcquisitionError on timeout.
        """
        if self._acquired:
            return self._lock_info  # type: ignore[return-value]

        deadline = time.time() + self._timeout
        last_error: str | None = None

        while time.time() < deadline:
            info = self._try_acquire()
            if info is not None:
                self._acquired = True
                self._lock_info = info
                self._start_renewal()
                self._register_cleanup()
                return info

            # Check for deadlock (lock held too long)
            existing = self._read_lock_info()
            if existing is not None:
                age = existing.age_seconds()
                if age > DEADLOCK_WARNING_S:
                    print(
                        f"[ledger-lock] ⚠️  Lock held for {age:.0f}s by PID {existing.pid} "
                        f"(operation={existing.operation!r})",
                        file=sys.stderr,
                    )
                if age > STALE_LOCK_S and not existing.is_process_alive():
                    print(
                        f"[ledger-lock] 🔓 Stale lock detected (PID {existing.pid} dead, "
                        f"held {age:.0f}s). Breaking lock.",
                        file=sys.stderr,
                    )
                    self._break_lock()
                    continue

            time.sleep(0.1)

        # Timeout
        existing = self._read_lock_info()
        holder = f"PID {existing.pid}" if existing else "unknown"
        raise LockAcquisitionError(
            f"Could not acquire ledger lock within {self._timeout}s "
            f"(held by {holder}). "
            f"Run: python3 bin/gac/ledger-lock-check.py"
        )

    def release(self) -> None:
        """Release the lock if held."""
        if not self._acquired:
            return

        self._stop_renewal()

        if self._fd is not None:
            try:
                # Release flock
                try:
                    import fcntl

                    fcntl.flock(self._fd, fcntl.LOCK_UN)
                except ImportError:
                    pass
                os.close(self._fd)
            except OSError:
                pass
            self._fd = None

        # Remove lock file
        try:
            self._lock_path.unlink(missing_ok=True)
        except OSError:
            pass

        self._acquired = False
        self._lock_info = None

    def __enter__(self) -> LedgerLock:
        self.acquire()
        return self

    def __exit__(self, *args: Any) -> None:
        self.release()

    def _try_acquire(self) -> LockInfo | None:
        """Attempt to acquire the lock. Returns LockInfo on success, None on failure."""
        lock_dir = self._lock_path.parent
        lock_dir.mkdir(parents=True, exist_ok=True)

        info = LockInfo(
            pid=os.getpid(),
            hostname=os.uname().nodename,
            acquired_at=time.time(),
            renewed_at=time.time(),
            operation=self._operation,
            metadata=self._metadata,
        )

        try:
            # Atomic create: O_CREAT|O_EXCL fails if file exists
            fd = os.open(
                str(self._lock_path),
                os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                0o644,
            )
        except FileExistsError:
            return None
        except OSError:
            return None

        try:
            # Try fcntl lock for cross-process advisory locking
            try:
                import fcntl

                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except (ImportError, BlockingIOError):
                # No fcntl or lock already held — fall back to file existence
                os.close(fd)
                try:
                    self._lock_path.unlink(missing_ok=True)
                except OSError:
                    pass
                return None

            # Write lock info
            os.write(fd, info.to_json().encode("utf-8"))
            os.fsync(fd)
            self._fd = fd
            return info

        except Exception:
            try:
                os.close(fd)
            except OSError:
                pass
            try:
                self._lock_path.unlink(missing_ok=True)
            except OSError:
                pass
            return None

    def _read_lock_info(self) -> LockInfo | None:
        """Read current lock info from the lock file."""
        try:
            text = self._lock_path.read_text(encoding="utf-8")
            return LockInfo.from_json(text)
        except (OSError, UnicodeDecodeError):
            return None

    def _break_lock(self) -> None:
        """Force-break a stale lock."""
        try:
            self._lock_path.unlink(missing_ok=True)
        except OSError:
            pass

    def _start_renewal(self) -> None:
        """Start background lock renewal."""
        self._renewal_thread = _RenewalWorker(
            lock_path=self._lock_path,
            interval=self._renewal_interval,
            lock_info=self._lock_info,
        )
        self._renewal_thread.daemon = True
        self._renewal_thread.start()

    def _stop_renewal(self) -> None:
        """Stop background lock renewal."""
        if self._renewal_thread is not None:
            self._renewal_thread.stop()
            self._renewal_thread = None

    def _register_cleanup(self) -> None:
        """Register atexit and signal handlers for automatic release."""
        if self._registered_cleanup:
            return
        self._registered_cleanup = True

        atexit.register(self.release)

        # Register signal handlers (save originals for restoration)
        for sig in (signal.SIGTERM, signal.SIGINT):
            try:
                original = signal.getsignal(sig)

                def _handler(signum: int, frame: Any, _orig: Any = original) -> None:
                    self.release()
                    if callable(_orig):
                        _orig(signum, frame)
                    elif _orig == signal.SIG_DFL:
                        signal.signal(signum, signal.SIG_DFL)
                        os.kill(os.getpid(), signum)

                signal.signal(sig, _handler)
            except (OSError, ValueError):
                pass  # Signal handling not available


class _RenewalWorker:
    """Background thread that renews the lock file periodically."""

    def __init__(
        self,
        lock_path: Path,
        interval: float,
        lock_info: LockInfo | None,
    ):
        self._lock_path = lock_path
        self._interval = interval
        self._lock_info = lock_info
        self._stop_event: Any = None
        self._thread: Any = None

    def start(self) -> None:
        import threading

        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._stop_event is not None:
            self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)

    def _run(self) -> None:
        while self._stop_event is not None and not self._stop_event.wait(self._interval):
            self._renew()

    def _renew(self) -> None:
        if self._lock_info is None:
            return
        self._lock_info.renewed_at = time.time()
        try:
            self._lock_path.write_text(
                self._lock_info.to_json(),
                encoding="utf-8",
            )
        except OSError:
            pass


def read_lock_status(lock_path: Path | None = None) -> dict[str, Any]:
    """Read and report lock status for monitoring.

    Returns a dict with:
      - locked: bool
      - info: LockInfo dict or None
      - stale: bool (lock held > STALE_LOCK_S and process dead)
      - deadlock_warning: bool (lock held > DEADLOCK_WARNING_S)
      - age_seconds: float or None
    """
    path = lock_path or LOCK_PATH
    result: dict[str, Any] = {
        "locked": False,
        "info": None,
        "stale": False,
        "deadlock_warning": False,
        "age_seconds": None,
    }

    if not path.exists():
        return result

    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        result["stale"] = True
        return result

    info = LockInfo.from_json(text)
    if info is None:
        result["stale"] = True
        return result

    result["locked"] = True
    result["info"] = {
        "pid": info.pid,
        "hostname": info.hostname,
        "acquired_at": info.acquired_at,
        "renewed_at": info.renewed_at,
        "operation": info.operation,
        "metadata": info.metadata,
    }
    result["age_seconds"] = info.age_seconds()
    result["deadlock_warning"] = info.age_seconds() > DEADLOCK_WARNING_S
    result["stale"] = (
        info.age_seconds() > STALE_LOCK_S and not info.is_process_alive()
    )

    return result


def break_stale_lock(lock_path: Path | None = None) -> bool:
    """Force-break a stale lock. Returns True if a lock was broken."""
    path = lock_path or LOCK_PATH
    status = read_lock_status(path)
    if not status["locked"]:
        return False
    if not status["stale"]:
        return False
    try:
        path.unlink(missing_ok=True)
        return True
    except OSError:
        return False
