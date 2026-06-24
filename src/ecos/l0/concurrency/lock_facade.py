"""ECOS L0 Lock Facade Protocol.

Defines the semantic L0 abstractions for distributed locks and concurrency control.
"""

from abc import ABC, abstractmethod
from contextlib import contextmanager
from typing import Iterator


class LockAcquireError(Exception):
    """Raised when a lock cannot be acquired within the timeout."""

    pass


class DistributedLock(ABC):
    """Base Protocol for distributed lock implementations."""

    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def acquire(self, timeout: float | None = None) -> bool:
        """Acquire the lock.

        Args:
            timeout: Maximum seconds to wait. None means wait forever.

        Returns:
            True if acquired, False otherwise (if implementation supports returning False instead of raising).

        Raises:
            LockAcquireError: If the lock cannot be acquired within the timeout.
        """
        pass

    @abstractmethod
    def release(self) -> None:
        """Release the lock."""
        pass

    @abstractmethod
    def check_and_set(self, expected_version: int, new_version: int) -> bool:
        """Optimistic locking. Only update if the current version matches expected_version.

        Args:
            expected_version: The version currently expected. 0 means ignore check.
            new_version: The new version to set upon success.

        Returns:
            True if successful, False if version conflict.
        """
        pass

    @contextmanager
    def lock(self, timeout: float | None = None) -> Iterator[None]:
        """Context manager for acquiring the lock."""
        self.acquire(timeout)
        try:
            yield
        finally:
            self.release()
