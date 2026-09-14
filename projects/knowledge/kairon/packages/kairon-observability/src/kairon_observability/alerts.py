"""AlertManager — rule-based alerting engine."""

from __future__ import annotations

import operator
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass
class AlertRule:
    """A named alerting rule with a condition expression and severity."""

    name: str
    condition: str
    severity: str = "warning"

    def __post_init__(self) -> None:
        if self.severity not in ("info", "warning", "critical"):
            raise ValueError(f"Unknown severity '{self.severity}'; use info/warning/critical")


@dataclass
class Alert:
    """A fired alert produced when a rule condition evaluates to true."""

    rule_name: str
    service: str
    metric: str
    current_value: float
    severity: str
    message: str
    fired_at: str = field(default_factory=lambda: datetime.now(tz=UTC).isoformat())


# ---------------------------------------------------------------------------
# Internal condition parser (restricted grammar for safety — no eval)
# ---------------------------------------------------------------------------
_OPS: dict[str, Any] = {
    ">": operator.gt,
    ">=": operator.ge,
    "<": operator.lt,
    "<=": operator.le,
    "==": operator.eq,
    "!=": operator.ne,
}

_COND_RE = re.compile(
    r"^\s*"
    r"(?P<metric>[a-zA-Z_][a-zA-Z0-9_]*)"
    r"\s*(?P<op>>=?|<=?|==|!=)\s*"
    r"(?P<threshold>-?\d+(?:\.\d+)?)"
    r"\s*$"
)


def _eval_condition(condition: str, metrics: dict[str, float]) -> bool:
    """Safely evaluate a simple ``metric op threshold`` condition against *metrics*."""
    m = _COND_RE.match(condition)
    if not m:
        raise ValueError(f"Invalid condition syntax: '{condition}'. Expected e.g. 'p99_ms > 500'")
    metric_name = m.group("metric")
    op_func = _OPS[m.group("op")]
    threshold = float(m.group("threshold"))
    current = metrics.get(metric_name)
    if current is None:
        return False  # missing metric → no alert
    return bool(op_func(current, threshold))


class AlertManager:
    """Collects alert rules and evaluates them against metric snapshots.

    Usage::

        mgr = AlertManager()
        mgr.add_rule(AlertRule("high-latency", "p99_ms > 500", "critical"))
        mgr.add_rule(AlertRule("low-avail", "availability_pct < 99.9", "warning"))
        alerts = mgr.check({"p99_ms": 520, "availability_pct": 99.5})
        for a in alerts:
            print(a.message)
    """

    def __init__(self) -> None:
        self._rules: list[AlertRule] = []

    def add_rule(self, rule: AlertRule) -> None:
        """Register an alerting rule."""
        self._rules.append(rule)

    def check(self, metrics: dict[str, float], service: str = "unknown") -> list[Alert]:
        """Evaluate all registered rules against *metrics*.

        Args:
            metrics: Dict of metric-name → current value.
            service: Optional service label attached to fired alerts.

        Returns:
            List of :class:`Alert` instances for every rule whose condition is met.
        """
        fired: list[Alert] = []
        for rule in self._rules:
            try:
                if _eval_condition(rule.condition, metrics):
                    # Determine which metric key triggered the rule
                    m = _COND_RE.match(rule.condition)
                    metric_name = m.group("metric") if m else "unknown"
                    current_val = metrics.get(metric_name, float("nan"))
                    alert = Alert(
                        rule_name=rule.name,
                        service=service,
                        metric=metric_name,
                        current_value=current_val,
                        severity=rule.severity,
                        message=(
                            f"[{rule.severity.upper()}] {rule.name}: "
                            f"{metric_name}={current_val} violates '{rule.condition}'"
                        ),
                    )
                    fired.append(alert)
            except ValueError:
                # Malformed rule — skip gracefully
                continue
        return fired
