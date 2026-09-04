"""Cockpit telemetry package."""

from .metrics import (
    MetricsCollector,
    get_metrics_collector,
    record_command_metric,
)

__all__ = [
    "MetricsCollector",
    "get_metrics_collector",
    "record_command_metric",
]
