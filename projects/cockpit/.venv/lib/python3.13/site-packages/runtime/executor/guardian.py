"""Guardian — execution monitor with policy enforcement, anomaly detection, and automated intervention."""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------


class AlertSeverity:
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AlertCategory:
    PERFORMANCE = "performance"
    BUDGET = "budget"
    FAILURE = "failure"
    GOVERNANCE = "governance"
    ANOMALY = "anomaly"


@dataclass
class GuardianAlert:
    id: str = ""
    severity: str = AlertSeverity.INFO
    category: str = AlertCategory.PERFORMANCE
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)
    timestamp: float = 0.0
    acknowledged: bool = False


@dataclass
class GuardianPolicy:
    name: str = ""
    enabled: bool = True
    check: Callable | None = None  # (context) -> GuardianAlert | None


@dataclass
class MonitoringContext:
    project_id: str = ""
    current_phase: str = ""
    phase_duration_ms: float = 0.0
    total_policy_checks: int = 0
    total_token_usage: int = 0
    token_budget: int = 0
    agent_failure_count: int = 0
    consecutive_failures: int = 0
    phase_retry_count: int = 0
    active_agents: int = 0


@dataclass
class GuardianConfig:
    enabled: bool = True
    check_interval_ms: float = 5000.0
    max_phase_duration_ms: float = 300_000.0
    token_budget_warning: float = 0.8
    max_consecutive_failures: int = 3
    max_alerts_history: int = 1000


@dataclass
class GuardianStats:
    total_alerts: int = 0
    by_severity: dict[str, int] = field(default_factory=dict)
    by_category: dict[str, int] = field(default_factory=dict)
    policies_count: int = 0
    is_running: bool = False


# ---------------------------------------------------------------------------
# Guardian
# ---------------------------------------------------------------------------


class Guardian:
    """Continuous monitoring engine with policy-based anomaly detection and intervention."""

    def __init__(self, config: GuardianConfig | None = None) -> None:
        self._config = config or GuardianConfig()
        self._alerts: list[GuardianAlert] = []
        self._policies: list[GuardianPolicy] = []
        self._contexts: dict[str, MonitoringContext] = {}
        self._running = False
        self._phase_starts: dict[str, float] = {}
        self._consecutive_failures: dict[str, int] = {}
        self._total_failures: dict[str, int] = {}

        self._register_default_policies()

    # -- Lifecycle -----------------------------------------------------------

    def start(self) -> None:
        if not self._config.enabled or self._running:
            return
        self._running = True

    def stop(self) -> None:
        self._running = False

    # -- Context management --------------------------------------------------

    def init_context(self, project_id: str, data: dict[str, Any] | None = None) -> MonitoringContext:
        data = data or {}
        ctx = MonitoringContext(
            project_id=project_id,
            current_phase=str(data.get("phase", "init")),
            token_budget=int(data.get("token_budget", 0)),
        )
        self._contexts[project_id] = ctx
        self._consecutive_failures[project_id] = 0
        self._total_failures[project_id] = 0
        return ctx

    def get_context(self, project_id: str) -> MonitoringContext | None:
        return self._contexts.get(project_id)

    def get_all_contexts(self) -> list[MonitoringContext]:
        return list(self._contexts.values())

    def remove_context(self, project_id: str) -> None:
        self._contexts.pop(project_id, None)
        self._phase_starts.pop(project_id, None)
        self._consecutive_failures.pop(project_id, None)
        self._total_failures.pop(project_id, None)

    # -- Policy management ---------------------------------------------------

    def add_policy(self, policy: GuardianPolicy) -> None:
        existing = next((p for p in self._policies if p.name == policy.name), None)
        if existing:
            self._policies.remove(existing)
        self._policies.append(policy)

    def remove_policy(self, name: str) -> None:
        self._policies[:] = [p for p in self._policies if p.name != name]

    def check_policies(self, context: MonitoringContext) -> list[GuardianAlert]:
        alerts: list[GuardianAlert] = []
        for policy in self._policies:
            if not policy.enabled or policy.check is None:
                continue
            try:
                alert = policy.check(context)
                if alert is not None:
                    self._record_alert(alert)
                    alerts.append(alert)
            except Exception:
                pass
        return alerts

    # -- Alerts --------------------------------------------------------------

    def raise_alert(self, severity: str, category: str, message: str, details: dict[str, Any] | None = None) -> GuardianAlert:
        alert = GuardianAlert(id=uuid.uuid4().hex[:12], severity=severity, category=category, message=message, details=details or {}, timestamp=time.time())
        self._record_alert(alert)
        return alert

    def acknowledge_alert(self, alert_id: str) -> bool:
        for a in self._alerts:
            if a.id == alert_id:
                a.acknowledged = True
                return True
        return False

    def get_alerts(self, severity: str | None = None, limit: int | None = None) -> list[GuardianAlert]:
        result = list(self._alerts)
        if severity is not None:
            result = [a for a in result if a.severity == severity]
        result.reverse()
        if limit is not None:
            result = result[:limit]
        return result

    def get_unacknowledged(self) -> list[GuardianAlert]:
        return sorted((a for a in self._alerts if not a.acknowledged), key=lambda x: x.timestamp, reverse=True)

    # -- Periodic checks -----------------------------------------------------

    def run_periodic_checks(self) -> list[GuardianAlert]:
        alerts: list[GuardianAlert] = []
        now = time.time()

        for project_id, ctx in list(self._contexts.items()):
            phase_start = self._phase_starts.get(project_id)
            if phase_start is not None:
                ctx.phase_duration_ms = (now - phase_start) * 1000
            alerts.extend(self.check_policies(ctx))

        return alerts

    # -- Stats ---------------------------------------------------------------

    def get_stats(self) -> GuardianStats:
        by_severity: dict[str, int] = {}
        by_category: dict[str, int] = {}

        for a in self._alerts:
            by_severity[a.severity] = by_severity.get(a.severity, 0) + 1
            by_category[a.category] = by_category.get(a.category, 0) + 1

        return GuardianStats(total_alerts=len(self._alerts), by_severity=by_severity, by_category=by_category, policies_count=len(self._policies), is_running=self._running)

    # -- Default policies ----------------------------------------------------

    def _register_default_policies(self) -> None:

        self.add_policy(GuardianPolicy(
            name="stuck-phase",
            check=lambda ctx: self._check_stuck_phase(ctx),
        ))
        self.add_policy(GuardianPolicy(
            name="token-budget",
            check=lambda ctx: self._check_token_budget(ctx),
        ))
        self.add_policy(GuardianPolicy(
            name="consecutive-failures",
            check=lambda ctx: self._check_failures(ctx),
        ))

    def _check_stuck_phase(self, ctx: MonitoringContext) -> GuardianAlert | None:
        max_dur = self._config.max_phase_duration_ms
        if ctx.phase_duration_ms >= max_dur:
            return GuardianAlert(severity=AlertSeverity.ERROR, category=AlertCategory.PERFORMANCE, message=f"Phase '{ctx.current_phase}' stuck ({ctx.phase_duration_ms:.0f}ms > {max_dur:.0f}ms)", details={"project_id": ctx.project_id, "duration_ms": ctx.phase_duration_ms}, timestamp=time.time())
        return None

    def _check_token_budget(self, ctx: MonitoringContext) -> GuardianAlert | None:
        if ctx.token_budget <= 0:
            return None
        ratio = ctx.total_token_usage / ctx.token_budget
        if ratio >= 1.0:
            return GuardianAlert(severity=AlertSeverity.CRITICAL, category=AlertCategory.BUDGET, message=f"Token budget exhausted ({ctx.total_token_usage}/{ctx.token_budget})", details={"project_id": ctx.project_id}, timestamp=time.time())
        if ratio >= self._config.token_budget_warning:
            return GuardianAlert(severity=AlertSeverity.WARNING, category=AlertCategory.BUDGET, message=f"Token budget at {ratio:.0%}", details={"project_id": ctx.project_id, "ratio": ratio}, timestamp=time.time())
        return None

    def _check_failures(self, ctx: MonitoringContext) -> GuardianAlert | None:
        if ctx.consecutive_failures >= self._config.max_consecutive_failures:
            return GuardianAlert(severity=AlertSeverity.ERROR, category=AlertCategory.FAILURE, message=f"{ctx.consecutive_failures} consecutive failures", details={"project_id": ctx.project_id}, timestamp=time.time())
        return None

    def _record_alert(self, alert: GuardianAlert) -> None:
        self._alerts.append(alert)
        while len(self._alerts) > self._config.max_alerts_history:
            self._alerts.pop(0)
