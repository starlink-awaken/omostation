"""SQLite-based Distributed Lock Implementation for ECOS."""

import sqlite3
import time
from pathlib import Path

from .lock_facade import DistributedLock, LockAcquireError

class SQLiteLock(DistributedLock):
    """Distributed lock implementation using SQLite."""

    def __init__(self, name: str, db_path: Path | str, lock_ttl: int = 60):
        super().__init__(name)
        self.db_path = Path(db_path)
        self.lock_ttl = lock_ttl
        self._init_db()
        self._acquired = False

    def _init_db(self):
        """Initialize the lock table if it doesn't exist."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path, timeout=5.0) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute('''
                CREATE TABLE IF NOT EXISTS locks (
                    name TEXT PRIMARY KEY,
                    expires_at REAL,
                    version INTEGER DEFAULT 0
                )
            ''')
            conn.commit()

    def acquire(self, timeout: float | None = None) -> bool:
        """Acquire the SQLite lock."""
        start = time.time()
        timeout = timeout if timeout is not None else 5.0
        
        while True:
            try:
                now = time.time()
                with sqlite3.connect(self.db_path, timeout=timeout) as conn:
                    # Try to acquire or steal expired lock
                    cursor = conn.execute("SELECT expires_at FROM locks WHERE name = ?", (self.name,))
                    row = cursor.fetchone()
                    
                    if row is None:
                        # Lock does not exist
                        conn.execute("INSERT INTO locks (name, expires_at) VALUES (?, ?)", (self.name, now + self.lock_ttl))
                        self._acquired = True
                        return True
                    else:
                        expires_at = row[0]
                        if now > expires_at:
                            # Lock expired, steal it
                            conn.execute("UPDATE locks SET expires_at = ? WHERE name = ?", (now + self.lock_ttl, self.name))
                            self._acquired = True
                            return True
            except sqlite3.OperationalError:
                pass # Database is locked by another connection
            
            if time.time() - start > timeout:
                raise LockAcquireError(f"Failed to acquire SQLiteLock({self.name}) within {timeout}s")
            
            time.sleep(0.1)

    def release(self) -> None:
        """Release the lock."""
        if not self._acquired:
            return
            
        with sqlite3.connect(self.db_path, timeout=5.0) as conn:
            conn.execute("UPDATE locks SET expires_at = 0 WHERE name = ?", (self.name,))
            conn.commit()
        self._acquired = False

    def check_and_set(self, expected_version: int, new_version: int) -> bool:
        """Optimistic locking implementation."""
        with sqlite3.connect(self.db_path, timeout=5.0) as conn:
            if expected_version == 0:
                conn.execute(
                    "INSERT INTO locks (name, expires_at, version) VALUES (?, 0, ?) "
                    "ON CONFLICT(name) DO UPDATE SET version = ?", 
                    (self.name, new_version, new_version)
                )
                conn.commit()
                return True
                
            cursor = conn.execute("SELECT version FROM locks WHERE name = ?", (self.name,))
            row = cursor.fetchone()
            current_version = row[0] if row else 0
            
            if current_version != expected_version:
                return False
                
            if row is None:
                conn.execute("INSERT INTO locks (name, expires_at, version) VALUES (?, 0, ?)", (self.name, new_version))
            else:
                conn.execute("UPDATE locks SET version = ? WHERE name = ?", (new_version, self.name))
            conn.commit()
            return True
