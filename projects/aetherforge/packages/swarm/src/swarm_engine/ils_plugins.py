from __future__ import annotations

import logging
from abc import abstractmethod

from ._compat import Infrastructure
from .ils_types import ActionIntent, Event

"""
---
Type: Organ
Status: ACTIVE
Version: 1.0.0
Owner: '@Sisyphus'
Layer: L3
Constraint: '[!!] AUTO_ADDED_METADATA'
Summary: 'Auto-generated metadata for ils_plugins.py'
Tags:
- auto-metadata
Authority: organs/D-Execution/AGENTS.md
---
"""

_log = logging.getLogger(__name__)
Type: Infrastructure

"""
Type: Infrastructure
Status: ACTIVE
Version: 0.0.0
Owner: '@Sisyphus'
Layer: L0-L2
Constraint: "[!!] AUTO_ADDED_METADATA"
Summary: 'Auto-added metadata for nucleus/Z-Microkernel/organs/ils_plugins.py'
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


class AuthorizerPlugin:
    """Abstract authorizer — decides permit/deny for an ActionIntent."""

    @abstractmethod
    def authorize(self, intent: ActionIntent, actor_layer: int) -> tuple[bool, str, str]:
        """
        Evaluate whether *intent* should be permitted.

        Returns:
            (permitted, reason, rule_id)
        """


class EventLoggerPlugin:
    """Abstract event logger — persists or forwards ILS audit events."""

    @abstractmethod
    def log(self, event: Event) -> None:
        """Persist or forward *event*."""


class HealthCheckerPlugin:
    """Abstract health checker — reports overall system load/health."""

    @abstractmethod
    def get_system_health(self) -> tuple[float, str]:
        """
        Return current system health.

        Returns:
            (health_score, status_description)
            health_score: 0.0 (fully degraded) … 1.0 (fully healthy).
        """
