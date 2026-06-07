from __future__ import annotations

"""
---
Type: Organ
Status: ACTIVE
Version: 0.0.0
Owner: '@Sisyphus'
Layer: L3
Constraint: "[!!] AUTO_ADDED_METADATA"
Summary: 'Auto-added metadata for organs/D-Execution/organs/ils_defaults.py'
Tags:
- auto-metadata
Authority: organs/D-Execution/AGENTS.md
---
"""


import logging

from .ils_plugins import AuthorizerPlugin, EventLoggerPlugin, HealthCheckerPlugin
from .ils_types import ActionIntent, Event

"""
Type: Infrastructure
Status: ACTIVE
Version: 0.0.0
Owner: '@Sisyphus'
Layer: L0-L2
Constraint: "[!!] AUTO_ADDED_METADATA"
Summary: 'Auto-added metadata for nucleus/Z-Microkernel/organs/ils_defaults.py'
Tags:
- auto-metadata

# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Microkernel_Component ≡ System_Bus
# 内涵 ≝ {Routing, Scheduling, Communication}
# 外延 ≝ {m | m ∈ Z-Microkernel ∧ orchestrates(m, Communication)}
# 功能 ⊢ {RouteMessages, ScheduleTasks, ManageBus}
# =============================================================================
"""

# duplicated from __future__ import annotations removed

_log = logging.getLogger(__name__)
# ---------------------------------------------------------------------------
# Read-only operations that are always permitted regardless of layer


# ---------------------------------------------------------------------------
# Read-only operations that are always permitted regardless of layer
# ---------------------------------------------------------------------------
_READ_OPS: frozenset[str] = frozenset({"read", "get", "list", "query", "ping", "validate", "health", "status"})


class DefaultAuthorizer(AuthorizerPlugin):
    """
    Layer-privilege authorizer.

    Layer privilege: lower number = higher privilege (L0 > L1 > L2 > L3 > L4).
    Rule:
      - Read-only ops are always permitted (cross-layer observability).
      - Write ops: actor at layer X may act on targets at layer >= X.
        (i.e. an actor may NOT write *up* to a more-privileged layer.)
    """

    def authorize(
        self,
        intent: ActionIntent,
        actor_layer: int,
    ) -> tuple[bool, str, str]:
        """Return (permitted, reason, rule_id)."""
        op = intent.operation.lower()

        # Read-ops: unrestricted
        if op in _READ_OPS:
            return True, "Read operation always permitted", "RULE-R001"

        # Write-ops: actor must be at same or higher privilege (lower numeric layer)
        if actor_layer <= intent.target_layer:
            return (
                True,
                f"Actor L{actor_layer} has privilege over target L{intent.target_layer}",
                "RULE-L001",
            )

        return (
            False,
            (f"Actor L{actor_layer} cannot write to L{intent.target_layer} (insufficient privilege)"),
            "RULE-L002",
        )


class DefaultEventLogger(EventLoggerPlugin):
    """In-memory event logger. Suitable for development and testing."""

    def __init__(self) -> None:
        super().__init__()
        self._events: list[Event] = []

    def log(self, event: Event) -> None:
        self._events.append(event)

    def get_events(self) -> list[Event]:
        """Return a snapshot of all logged events."""
        return list(self._events)

    def clear(self) -> None:
        """Discard all buffered events."""
        self._events.clear()


class DefaultHealthChecker(HealthCheckerPlugin):
    """
    Baseline health checker — always reports fully healthy.

    Replace with a real implementation that inspects CPU / memory load,
    queue depths, etc. when running in production.
    """

    def get_system_health(self) -> tuple[float, str]:
        """Return (1.0, 'healthy') unconditionally."""
        return 1.0, "healthy"
