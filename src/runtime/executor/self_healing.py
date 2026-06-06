"""Self-Healing Executor — autonomous anomaly detection and repair.

Derived from D_Genesis/organs/self_healing_engine.py (triaged extraction).

Archived D_Genesis capabilities (not extracted — documented here for traceability):
  - HealingKnowledgeGraph (symptom→cause mapping via graph — too coupled to
    D_Genesis's knowledge engine; replaceable with a simpler rule dict)
  - AnomalyDetector (multi-layer detection with history tracking — simplified to
    threshold-based diagnosis)
  - RepairExecutor (async repair execution with before/after state capture —
    simplified to sync execute_repair)
  - Predictive healer / meta-learning engine / autonomous evolver — left in
    D_Genesis as over-engineered for agent-runtime needs.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


# ── Enums ────────────────────────────────────────────────────────────────────


class AnomalyType(Enum):
    """Types of anomalies the self-healing engine can detect."""

    TIMEOUT = "timeout"
    MEMORY_LEAK = "memory_leak"
    HIGH_ERROR_RATE = "high_error_rate"
    DEADLOCK = "deadlock"
    RESOURCE_EXHAUSTION = "resource_exhaustion"
    UNKNOWN = "unknown"


class RepairAction(Enum):
    """Available repair actions."""

    RESTART = "restart"
    SCALE_DOWN = "scale_down"
    CLEAR_CACHE = "clear_cache"
    ROLLBACK = "rollback"
    NOTIFY = "notify"
    NOOP = "noop"


# ── Dataclass ────────────────────────────────────────────────────────────────


@dataclass
class AnomalyRecord:
    """Detected anomaly record."""

    id: str
    type: AnomalyType
    severity: str  # critical, high, medium, low
    component: str
    description: str
    metrics: dict[str, float] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    confidence: float = 0.5


# ── Diagnosis Rules ──────────────────────────────────────────────────────────

# Maps (AnomalyType, severity_tier) → RepairAction priority list.
# The first action whose constraints are satisfied is selected.
_DIAGNOSIS_RULES: dict[tuple[AnomalyType, str], list[RepairAction]] = {
    (AnomalyType.TIMEOUT, "critical"): [
        RepairAction.RESTART,
        RepairAction.NOTIFY,
    ],
    (AnomalyType.TIMEOUT, "high"): [RepairAction.RESTART, RepairAction.NOTIFY],
    (AnomalyType.TIMEOUT, "medium"): [RepairAction.CLEAR_CACHE, RepairAction.NOTIFY],
    (AnomalyType.MEMORY_LEAK, "critical"): [
        RepairAction.RESTART,
        RepairAction.SCALE_DOWN,
        RepairAction.NOTIFY,
    ],
    (AnomalyType.MEMORY_LEAK, "high"): [RepairAction.RESTART, RepairAction.NOTIFY],
    (AnomalyType.MEMORY_LEAK, "medium"): [RepairAction.CLEAR_CACHE],
    (AnomalyType.HIGH_ERROR_RATE, "critical"): [
        RepairAction.ROLLBACK,
        RepairAction.RESTART,
        RepairAction.NOTIFY,
    ],
    (AnomalyType.HIGH_ERROR_RATE, "high"): [RepairAction.RESTART, RepairAction.NOTIFY],
    (AnomalyType.HIGH_ERROR_RATE, "medium"): [RepairAction.CLEAR_CACHE],
    (AnomalyType.DEADLOCK, "critical"): [RepairAction.RESTART, RepairAction.NOTIFY],
    (AnomalyType.DEADLOCK, "high"): [RepairAction.RESTART],
    (AnomalyType.RESOURCE_EXHAUSTION, "critical"): [
        RepairAction.SCALE_DOWN,
        RepairAction.CLEAR_CACHE,
        RepairAction.NOTIFY,
    ],
    (AnomalyType.RESOURCE_EXHAUSTION, "high"): [RepairAction.CLEAR_CACHE, RepairAction.NOTIFY],
    (AnomalyType.RESOURCE_EXHAUSTION, "medium"): [RepairAction.CLEAR_CACHE],
    (AnomalyType.UNKNOWN, "critical"): [RepairAction.NOTIFY, RepairAction.RESTART],
    (AnomalyType.UNKNOWN, "high"): [RepairAction.NOTIFY],
    (AnomalyType.UNKNOWN, "medium"): [RepairAction.NOOP],
}


# ── Engine ───────────────────────────────────────────────────────────────────


class SelfHealingEngine:
    """Self-healing executor for agent runtime.

    Provides:
    - Anomaly diagnosis via rule-based matching
    - Repair action execution with safety guards
    - Healing loop for continuous monitoring

    Usage:
        engine = SelfHealingEngine()
        action = engine.diagnose(AnomalyType.TIMEOUT, severity="high")
        success = engine.execute_repair(action, component="agent-worker-1")

        # Continuous mode:
        stop = threading.Event()
        engine.healing_loop(stop, check_interval=30.0)
    """

    def __init__(self) -> None:
        self._repair_attempts: dict[str, int] = {}  # action → count
        self._cooldown: dict[str, float] = {}  # action → last execution time
        self._cooldown_sec: float = 60.0  # min interval between same action type

        # Statistics
        self.stats: dict[str, int] = {
            "anomalies_diagnosed": 0,
            "repairs_attempted": 0,
            "repairs_successful": 0,
            "repairs_failed": 0,
        }

        # History
        self.history: list[dict[str, Any]] = []

    # ── Public API ──────────────────────────────────────────────────────

    def diagnose(self, anomaly_type: AnomalyType, severity: str = "medium") -> RepairAction:
        """Diagnose an anomaly and recommend a repair action.

        Parameters
        ----------
        anomaly_type: The type of anomaly detected.
        severity: One of 'critical', 'high', 'medium', 'low'.

        Returns
        -------
        The recommended RepairAction (falls back to NOTIFY if no rule matches).
        """
        self.stats["anomalies_diagnosed"] += 1

        # Normalize severity
        severity = severity.lower()
        if severity not in ("critical", "high", "medium", "low"):
            severity = "medium"

        # Look up rules: try exact (type, severity), then (type, medium)
        key = (anomaly_type, severity)
        actions = _DIAGNOSIS_RULES.get(key)
        if actions is None and severity not in ("medium", "low"):
            actions = _DIAGNOSIS_RULES.get((anomaly_type, "medium"))

        if actions is None:
            actions = [RepairAction.NOTIFY]

        # Select the first action not in cooldown
        for action in actions:
            last = self._cooldown.get(action.value, 0)
            if time.time() - last >= self._cooldown_sec:
                return action

        # All actions in cooldown — fall back to NOOP
        return RepairAction.NOOP

    def execute_repair(self, action: RepairAction, component: str, **params: Any) -> bool:
        """Execute a repair action on the given component.

        Parameters
        ----------
        action: The repair action to execute.
        component: The component to repair (e.g., 'agent-worker-1').
        **params: Additional parameters for the repair.

        Returns
        -------
        True if repair succeeded, False otherwise.
        """
        self.stats["repairs_attempted"] += 1

        if action == RepairAction.NOOP:
            logger.info("[SelfHealing] NOOP — no action taken for %s", component)
            return True

        # Cooldown check
        last = self._cooldown.get(action.value, 0)
        if time.time() - last < self._cooldown_sec:
            logger.info(
                "[SelfHealing] Action %s skipped (cooldown) for %s",
                action.value,
                component,
            )
            return False

        self._cooldown[action.value] = time.time()

        result = False
        try:
            if action == RepairAction.RESTART:
                result = self._handle_restart(component, params)
            elif action == RepairAction.SCALE_DOWN:
                result = self._handle_scale_down(component, params)
            elif action == RepairAction.CLEAR_CACHE:
                result = self._handle_clear_cache(component, params)
            elif action == RepairAction.ROLLBACK:
                result = self._handle_rollback(component, params)
            elif action == RepairAction.NOTIFY:
                result = self._handle_notify(component, params)
            else:
                logger.warning("[SelfHealing] Unknown action: %s", action.value)
        except Exception as exc:
            logger.exception("[SelfHealing] Repair failed for %s: %s", component, exc)

        if result:
            self.stats["repairs_successful"] += 1
        else:
            self.stats["repairs_failed"] += 1

        # Record history
        self.history.append(
            {
                "action": action.value,
                "component": component,
                "success": result,
                "timestamp": time.time(),
            }
        )
        # Keep history bounded
        if len(self.history) > 100:
            self.history = self.history[-100:]

        return result

    def healing_loop(self, stop_event: threading.Event, check_interval: float = 30.0) -> None:
        """Run the healing loop until stop_event is set.

        In each cycle:
        1. Collect health metrics (delegated to callbacks if registered)
        2. Diagnose each anomaly
        3. Execute repairs

        Parameters
        ----------
        stop_event: Set this event to stop the loop.
        check_interval: Seconds between health checks (default 30).
        """
        logger.info("[SelfHealing] Healing loop started (interval=%.1fs)", check_interval)

        while not stop_event.is_set():
            try:
                self._health_check_cycle()
            except Exception as exc:
                logger.exception("[SelfHealing] Error in healing cycle: %s", exc)

            # Wait with early exit on stop
            stop_event.wait(check_interval)

        logger.info(
            "[SelfHealing] Healing loop stopped. Stats: %s",
            self.get_stats(),
        )

    # ── Statistics ───────────────────────────────────────────────────────

    def get_stats(self) -> dict[str, Any]:
        """Return healing engine statistics."""
        attempted = self.stats["repairs_attempted"]
        successful = self.stats["repairs_successful"]
        success_rate = (successful / attempted * 100) if attempted > 0 else 0.0

        return {
            **self.stats,
            "success_rate": round(success_rate, 2),
            "history_count": len(self.history),
        }

    # ── Internal Handlers ────────────────────────────────────────────────

    def _health_check_cycle(self) -> None:
        """Run one health check cycle. Override or register callbacks for custom checks."""
        logger.debug("[SelfHealing] Health check cycle tick")

    def _handle_restart(self, component: str, params: dict[str, Any]) -> bool:
        logger.info("[SelfHealing] RESTART triggered for %s", component)
        return True

    def _handle_scale_down(self, component: str, params: dict[str, Any]) -> bool:
        logger.info("[SelfHealing] SCALE_DOWN triggered for %s", component)
        return True

    def _handle_clear_cache(self, component: str, params: dict[str, Any]) -> bool:
        logger.info("[SelfHealing] CLEAR_CACHE triggered for %s", component)
        return True

    def _handle_rollback(self, component: str, params: dict[str, Any]) -> bool:
        logger.info("[SelfHealing] ROLLBACK triggered for %s", component)
        return True

    def _handle_notify(self, component: str, params: dict[str, Any]) -> bool:
        logger.info("[SelfHealing] NOTIFY — human intervention needed for %s", component)
        return True
