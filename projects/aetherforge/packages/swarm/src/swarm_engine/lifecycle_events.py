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
# Events ≡ Module
# 内涵 ≝ {Events}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, Events)}
# 功能 ⊢ {Init_Events, Execute_Events, Validate_Events}
# =============================================================================

"""
---
Type: Engine Submodule
Status: ACTIVE
Layer: L3
Summary: SwarmEventEmitter — EventBus integration for lifecycle events.
  Extracted from SwarmLifecycleManager._emit_lifecycle_event().
Version: 1.0.0
Authority: organs/D-Execution/AGENTS.md
---

Responsibility: Single — emit lifecycle events on the EventBus.
Best-effort only; never disrupts core logic.
"""

import logging
from typing import Any

_log = logging.getLogger(__name__)


class SwarmEventEmitter:
    """
    Thin EventBus integration for swarm lifecycle events.

    Responsibility: Single — publish events to the EventBus.
    All failures are silently swallowed so the event layer never
    disrupts the core lifecycle logic.
    """

    SOURCE_NAME = "swarm_lifecycle_manager"

    def __init__(self) -> None:
        pass

    # ─── Public API ───────────────────────────────────────────────────────────

    def emit(
        self,
        event_type: str,
        payload: dict[str, Any],
    ) -> None:
        """Emit a lifecycle event on the EventBus. Best-effort; never raises."""
        try:
            from kairon_events import get_global_event_bus, make_event
        except (ImportError, OSError, RuntimeError) as _exc:
            _log.debug(
                "[SwarmEventEmitter] kairon_events unavailable: %s",
                _exc,
            )
            return

        try:
            bus = get_global_event_bus()
            if bus is None:
                _log.debug("[SwarmEventEmitter] Global EventBus not yet registered")
                return
            bus.publish(make_event(event_type, self.SOURCE_NAME, payload))
        except (AttributeError, RuntimeError, TypeError, ValueError) as _exc:
            _log.debug(
                "[SwarmEventEmitter] Event publish failed for '%s': %s",
                event_type,
                _exc,
            )
