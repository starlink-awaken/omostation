"""Tests for kairon_observability — importability and basic smoke tests."""
# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false


class TestImports:
    """Verify all modules are importable."""

    def test_import_metrics(self):
        from kairon_observability.metrics import MetricsCollector

        collector = MetricsCollector()
        assert collector is not None

    def test_import_alerts(self):
        from kairon_observability.alerts import AlertManager

        mgr = AlertManager()
        assert mgr is not None

    def test_import_anomaly(self):
        from kairon_observability.anomaly import AnomalyDetector

        detector = AnomalyDetector(window_size=10)
        assert detector is not None

    def test_import_dashboard(self):
        from kairon_observability.dashboard import DashboardData

        data = DashboardData()
        assert data is not None

    def test_import_slo(self):
        from kairon_observability.slo import SLOTracker

        tracker = SLOTracker()
        assert tracker is not None

    def test_import_monitoring_metrics(self):
        from kairon_observability.monitoring_metrics import HarvestMetrics

        metrics = HarvestMetrics()
        assert metrics is not None
