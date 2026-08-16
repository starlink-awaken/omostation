"""Retention Policy — decide whether an entry should be kept or collected."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta


class RetentionPolicy:
    """Evaluates whether a memory entry should be retained.

    Supports two rule dimensions:

    * **TTL-based**: entries older than a configured TTL expire.
    * **Importance-based**: entries with importance below a threshold are
      candidates for collection.

    Rules are passed as a dict::

        {
            "ttl_days": 90,
            "min_importance": 0.3,
            "pinned_ids": ["abc"],
        }

    Typical usage::

        policy = RetentionPolicy()
        keep = policy.should_keep(entry, {"ttl_days": 30, "min_importance": 0.5})
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def should_keep(self, entry: dict, policy_rules: dict) -> bool:
        """Return True if the entry should be retained under *policy_rules*.

        Args:
            entry: A dict representing the entry. Expected keys vary by rule:
                - ``created_at`` / ``updated_at``: ISO timestamp for TTL.
                - ``importance``: float 0-1 for importance threshold.
                - ``id``: str for pin-list checking.
            policy_rules: A dict specifying retention rules. Supported keys:
                - ``ttl_days``: int — max age in days before expiry.
                - ``min_importance``: float — entries below this are collected.
                - ``pinned_ids``: list[str] — these IDs are always kept.

        Returns:
            True if the entry should be retained.
        """
        # Pinned entries are always kept
        pinned = policy_rules.get("pinned_ids", [])
        if entry.get("id") in pinned:
            return True

        # --- TTL check ---
        ttl_days = policy_rules.get("ttl_days")
        if ttl_days is not None and not self._check_ttl(entry, int(ttl_days)):
            return False

        # --- Importance check ---
        min_importance = policy_rules.get("min_importance")
        if min_importance is not None and not self._check_importance(entry, float(min_importance)):
            return False

        return True

    # ------------------------------------------------------------------
    # Rule helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _check_ttl(entry: dict, ttl_days: int) -> bool:
        """Return True if the entry is within its TTL window."""
        timestamp_raw = entry.get("created_at") or entry.get("updated_at")
        if timestamp_raw is None:
            # No timestamp → cannot determine age → keep
            return True
        try:
            timestamp = datetime.fromisoformat(str(timestamp_raw))
        except (ValueError, TypeError):
            return True
        cutoff = datetime.now(UTC) - timedelta(days=ttl_days)
        return timestamp >= cutoff

    @staticmethod
    def _check_importance(entry: dict, min_importance: float) -> bool:
        """Return True if the entry meets the importance threshold."""
        importance = entry.get("importance")
        if importance is None:
            # No importance score → keep (conservative default)
            return True
        try:
            return float(importance) >= min_importance
        except (TypeError, ValueError):
            return True
