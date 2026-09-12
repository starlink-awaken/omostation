"""Health monitoring cartridge: continuous vitals, anomaly alerts, visit cards.

Entry points:
  domain.health.monitor_pipeline.run_daily  — daily aggregate + anomaly scan
  domain.health.test_monitor_pipeline       — self-test (`python -m ...`)
"""

from .monitor_pipeline import (
    Finding,
    InterventionCard,
    build_intervention_card,
    daily_health_score,
    detect_anomalies,
    run_daily,
)
from .vitals import METRICS, PersonalBaseline, VitalReading, build_ledger

__all__ = [
    "METRICS",
    "Finding",
    "InterventionCard",
    "PersonalBaseline",
    "VitalReading",
    "build_intervention_card",
    "build_ledger",
    "daily_health_score",
    "detect_anomalies",
    "run_daily",
]
