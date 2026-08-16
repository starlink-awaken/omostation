"""kairon-observability — Monitoring and observability toolkit for kairon.

Provides metrics collection (Prometheus-style), alerting, anomaly detection,
health dashboards, and SLI/SLO tracking.
"""

from kairon_observability.alerts import Alert, AlertManager, AlertRule
from kairon_observability.anomaly import AnomalyDetector
from kairon_observability.dashboard import DashboardConfig, DashboardData, ServiceCard, TopologyEdge
from kairon_observability.metrics import MetricsCollector
from kairon_observability.monitoring_metrics import HarvestMetrics
from kairon_observability.slo import SLOBreach, SLODefinition, SLOTracker

__all__ = [
    # alerts
    "Alert",
    "AlertManager",
    "AlertRule",
    # anomaly
    "AnomalyDetector",
    # dashboard
    "DashboardConfig",
    "DashboardData",
    "ServiceCard",
    "TopologyEdge",
    # metrics
    "MetricsCollector",
    # monitoring
    "HarvestMetrics",
    # slo
    "SLODefinition",
    "SLOBreach",
    "SLOTracker",
    "get_tracer",
    "setup_tracing",
]
from .tracing import get_tracer, setup_tracing
