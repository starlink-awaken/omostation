"""Deterministic conflict resolution for D_Execution."""

from __future__ import annotations

from typing import Any


class DeterministicConflictResolver:
    """Resolves conflicts between two versions of a data key.

    Supports multiple strategies:
    - ``last_writer_wins``: picks the value with the higher ``_timestamp``.
    - ``vector_clock``: picks the value with the higher vector-clock sum.
    - ``priority``: picks the value with the higher ``_priority``.
    - ``merge``: attempts a semantic merge (falls back to last-writer-wins).
    """

    VALID_STRATEGIES = frozenset({"last_writer_wins", "vector_clock", "priority", "merge"})

    def __init__(self, strategy: str = "last_writer_wins") -> None:
        if strategy not in self.VALID_STRATEGIES:
            msg = f"Unknown conflict resolution strategy: {strategy!r}"
            raise ValueError(msg)
        self.strategy = strategy

    def resolve(
        self,
        left: dict[str, Any],
        right: dict[str, Any],
        key: str,
        **kwargs: Any,
    ) -> Any:
        """Resolve a conflict between two values for *key*.

        Args:
            left: First version dict (may contain meta fields like
                ``_timestamp``, ``_vector_clock``, ``_priority``).
            right: Second version dict.
            key: The key whose value is in conflict.
            **kwargs: Passed through to the strategy-specific method.

        Returns:
            The resolved value for *key*.
        """
        resolve_fn = getattr(self, f"_resolve_{self.strategy}", self._resolve_last_writer_wins)
        return resolve_fn(left, right, key, **kwargs)

    def _resolve_last_writer_wins(
        self,
        left: dict[str, Any],
        right: dict[str, Any],
        key: str,
        **kwargs: Any,
    ) -> Any:
        left_ts = left.get("_timestamp", 0)
        right_ts = right.get("_timestamp", 0)
        return right[key] if right_ts >= left_ts else left[key]

    def _resolve_vector_clock(
        self,
        left: dict[str, Any],
        right: dict[str, Any],
        key: str,
        **kwargs: Any,
    ) -> Any:
        left_sum = sum(left.get("_vector_clock", {}).values())
        right_sum = sum(right.get("_vector_clock", {}).values())
        return right[key] if right_sum >= left_sum else left[key]

    def _resolve_priority(
        self,
        left: dict[str, Any],
        right: dict[str, Any],
        key: str,
        **kwargs: Any,
    ) -> Any:
        left_prio = left.get("_priority", 0)
        right_prio = right.get("_priority", 0)
        return right[key] if right_prio >= left_prio else left[key]

    def _resolve_merge(
        self,
        left: dict[str, Any],
        right: dict[str, Any],
        key: str,
        **kwargs: Any,
    ) -> Any:
        # Merge is a best-effort strategy; fall back to last-writer-wins.
        return self._resolve_last_writer_wins(left, right, key, **kwargs)
