"""Conflict arbitrator for D_Execution.

Resolves competing claims over shared resources using configurable
deterministic policies.
"""

from __future__ import annotations

from typing import Any


class ConflictArbitrator:
    """Resolves conflicts between competing task claims or resource
    allocations.

    Policies:
    - ``priority_first``: highest ``priority`` value wins (default).
    - ``fifo``: earliest ``created_at`` / ``timestamp`` wins.
    - ``round_robin``: cyclically distributes via hash of the resource key.
    """

    VALID_POLICIES = frozenset({"priority_first", "fifo", "round_robin"})

    def __init__(self, policy: str = "priority_first") -> None:
        if policy not in self.VALID_POLICIES:
            msg = f"Unknown arbitration policy: {policy!r}"
            raise ValueError(msg)
        self.policy = policy

    def arbitrate(
        self,
        claims: list[dict[str, Any]],
        resource_key: str = "",
    ) -> dict[str, Any] | None:
        """Select a winning claim from competing claims for a resource.

        Args:
            claims: List of claim dicts. Each should contain at minimum
                ``"worker_id"`` and ``"task_id"``.
            resource_key: Identifier for the contended resource. Used by
                the ``round_robin`` policy for deterministic hashing.

        Returns:
            The winning claim dict, or ``None`` if the list is empty.
        """
        if not claims:
            return None

        fn = getattr(self, f"_policy_{self.policy}", self._policy_priority_first)
        return fn(claims, resource_key)

    def validate_claim(self, claim: dict[str, Any]) -> bool:
        """Check whether a claim dict has the required fields."""
        return "worker_id" in claim and "task_id" in claim

    def _policy_priority_first(
        self,
        claims: list[dict[str, Any]],
        _resource_key: str = "",
    ) -> dict[str, Any]:
        return max(claims, key=lambda c: c.get("priority", 0))

    def _policy_fifo(
        self,
        claims: list[dict[str, Any]],
        _resource_key: str = "",
    ) -> dict[str, Any]:
        return min(claims, key=lambda c: c.get("created_at", c.get("timestamp", 0)))

    def _policy_round_robin(
        self,
        claims: list[dict[str, Any]],
        resource_key: str = "",
    ) -> dict[str, Any]:
        idx = hash(resource_key) % len(claims) if resource_key else 0
        return claims[idx]
