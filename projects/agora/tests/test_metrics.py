"""Tests for Agora metrics module."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest
from agora.metrics import (
    PipelineExecution,
    PipelineMetricsCollector,
    get_all_pipeline_metrics,
    get_completion_rate,
    get_pipeline_collector,
    record_execution,
)
from agora.metrics.collector import PipelineMetrics

# ============================================================================
# PipelineExecution
# ============================================================================


class TestPipelineExecution:
    def test_create_basic(self):
        ex = PipelineExecution(
            name="test-pipeline",
            timestamp="2025-01-01T00:00:00",
            steps=[{"name": "step1", "duration": 1.0}],
            completed=True,
            total_duration=1.0,
        )
        assert ex.name == "test-pipeline"
        assert ex.completed is True
        assert ex.total_duration == 1.0

    def test_create_not_completed(self):
        ex = PipelineExecution(
            name="fail-pipeline",
            timestamp="2025-01-01T00:00:00",
            steps=[],
            completed=False,
            total_duration=0.0,
        )
        assert ex.completed is False


# ============================================================================
# PipelineMetrics
# ============================================================================


class TestPipelineMetrics:
    def test_defaults(self):
        m = PipelineMetrics()
        assert m.total_executions == 0
        assert m.successful_executions == 0
        assert m.failed_executions == 0
        assert m.total_duration == 0.0
        assert m.recent_executions == []
        assert m.pipeline_stats == {}

    def test_completion_rate_zero(self):
        m = PipelineMetrics()
        assert m.completion_rate == 0.0

    def test_completion_rate_perfect(self):
        m = PipelineMetrics(total_executions=10, successful_executions=10)
        assert m.completion_rate == 100.0

    def test_completion_rate_partial(self):
        m = PipelineMetrics(total_executions=10, successful_executions=7)
        assert m.completion_rate == 70.0

    def test_get_pipeline_completion_rate_unknown(self):
        m = PipelineMetrics()
        assert m.get_pipeline_completion_rate("nonexistent") == 0.0

    def test_get_pipeline_completion_rate_zero_total(self):
        m = PipelineMetrics(pipeline_stats={"p1": {"total": 0, "successful": 0}})
        assert m.get_pipeline_completion_rate("p1") == 0.0

    def test_get_pipeline_completion_rate_valid(self):
        m = PipelineMetrics(pipeline_stats={"p1": {"total": 10, "successful": 8, "failed": 2, "total_duration": 50.0}})
        assert m.get_pipeline_completion_rate("p1") == 80.0

    def test_get_average_duration_no_pipeline_name_empty(self):
        m = PipelineMetrics()
        assert m.get_average_duration() == 0.0

    def test_get_average_duration_no_pipeline_name(self):
        m = PipelineMetrics(total_executions=4, total_duration=20.0)
        assert m.get_average_duration() == 5.0

    def test_get_average_duration_specific_unknown(self):
        m = PipelineMetrics()
        assert m.get_average_duration("p1") == 0.0

    def test_get_average_duration_specific_zero_total(self):
        m = PipelineMetrics(pipeline_stats={"p1": {"total": 0, "total_duration": 0.0}})
        assert m.get_average_duration("p1") == 0.0

    def test_get_average_duration_specific(self):
        m = PipelineMetrics(pipeline_stats={"p1": {"total": 4, "total_duration": 20.0, "successful": 0, "failed": 0}})
        assert m.get_average_duration("p1") == 5.0


# ============================================================================
# PipelineMetricsCollector — Fixtures
# ============================================================================


@pytest.fixture
def tmp_collector():
    """Create a fresh collector with a temp storage path."""
    tmp = tempfile.mkdtemp()
    return PipelineMetricsCollector(storage_path=tmp), tmp


# ============================================================================
# PipelineMetricsCollector — Init & Persistence
# ============================================================================


class TestCollectorInit:
    def test_default_storage_path(self):
        c = PipelineMetricsCollector(storage_path=tempfile.mkdtemp())
        assert c.metrics.total_executions == 0
        assert c.storage_path.exists()

    def test_loads_existing_data(self):
        tmp = tempfile.mkdtemp()
        metrics_file = Path(tmp) / "pipeline.json"
        data = {
            "total_executions": 5,
            "successful_executions": 4,
            "failed_executions": 1,
            "total_duration": 10.0,
            "recent_executions": [],
            "pipeline_stats": {},
        }
        with open(metrics_file, "w") as f:
            json.dump(data, f)

        c = PipelineMetricsCollector(storage_path=tmp)
        assert c.metrics.total_executions == 5
        assert c.metrics.successful_executions == 4

    def test_loads_corrupted_data_gracefully(self):
        tmp = tempfile.mkdtemp()
        metrics_file = Path(tmp) / "pipeline.json"
        with open(metrics_file, "w") as f:
            f.write("invalid json{")

        c = PipelineMetricsCollector(storage_path=tmp)
        assert c.metrics.total_executions == 0  # falls back to fresh


# ============================================================================
# PipelineMetricsCollector — Record
# ============================================================================


class TestCollectorRecord:
    def test_record_successful(self, tmp_collector):
        c, _ = tmp_collector
        c.record_pipeline_execution("test-pipe", [{"name": "step1", "duration": 1.0}], completed=True)

        assert c.metrics.total_executions == 1
        assert c.metrics.successful_executions == 1
        assert c.metrics.failed_executions == 0
        assert c.metrics.total_duration == 1.0

    def test_record_failed(self, tmp_collector):
        c, _ = tmp_collector
        c.record_pipeline_execution("fail-pipe", [{"name": "step1", "duration": 0.5}], completed=False)

        assert c.metrics.total_executions == 1
        assert c.metrics.successful_executions == 0
        assert c.metrics.failed_executions == 1

    def test_record_multiple(self, tmp_collector):
        c, _ = tmp_collector
        c.record_pipeline_execution("p1", [{"duration": 1.0}], completed=True)
        c.record_pipeline_execution("p2", [{"duration": 2.0}], completed=False)
        c.record_pipeline_execution("p1", [{"duration": 3.0}], completed=True)

        assert c.metrics.total_executions == 3
        assert c.metrics.successful_executions == 2
        assert c.metrics.failed_executions == 1
        assert c.metrics.total_duration == 6.0

    def test_record_updates_pipeline_stats(self, tmp_collector):
        c, _ = tmp_collector
        c.record_pipeline_execution("p1", [{"duration": 1.0}], completed=True)
        c.record_pipeline_execution("p1", [{"duration": 2.0}], completed=False)

        stats = c.metrics.pipeline_stats["p1"]
        assert stats["total"] == 2
        assert stats["successful"] == 1
        assert stats["failed"] == 1
        assert stats["total_duration"] == 3.0

    def test_record_creates_execution_entry(self, tmp_collector):
        c, _ = tmp_collector
        c.record_pipeline_execution("p1", [{"name": "step1"}], completed=True)

        assert len(c.metrics.recent_executions) == 1
        ex = c.metrics.recent_executions[0]
        assert ex.name == "p1"
        assert ex.completed is True

    def test_record_persists_to_disk(self, tmp_collector):
        c, tmp = tmp_collector
        c.record_pipeline_execution("p1", [], completed=True)

        # Re-load from disk
        c2 = PipelineMetricsCollector(storage_path=tmp)
        assert c2.metrics.total_executions == 1


# ============================================================================
# PipelineMetricsCollector — Query
# ============================================================================


class TestCollectorQuery:
    def test_get_completion_rate_empty(self, tmp_collector):
        c, _ = tmp_collector
        assert c.get_completion_rate() == 0.0

    def test_get_completion_rate_specific(self, tmp_collector):
        c, _ = tmp_collector
        c.record_pipeline_execution("p1", [], completed=True)
        c.record_pipeline_execution("p1", [], completed=False)
        c.record_pipeline_execution("p2", [], completed=True)

        assert c.get_completion_rate("p1") == 50.0
        assert c.get_completion_rate("p2") == 100.0

    def test_get_average_duration_empty(self, tmp_collector):
        c, _ = tmp_collector
        assert c.get_average_duration() == 0.0

    def test_get_average_duration_specific(self, tmp_collector):
        c, _ = tmp_collector
        c.record_pipeline_execution("p1", [{"duration": 2.0}, {"duration": 3.0}], True)
        assert c.get_average_duration("p1") == 5.0  # total_duration = 5

    def test_get_recent_executions_all(self, tmp_collector):
        c, _ = tmp_collector
        for i in range(5):
            c.record_pipeline_execution(f"p{i}", [], True)

        recent = c.get_recent_executions(limit=3)
        assert len(recent) == 3
        assert recent[-1].name == "p4"

    def test_get_recent_executions_filtered(self, tmp_collector):
        c, _ = tmp_collector
        c.record_pipeline_execution("p1", [], True)
        c.record_pipeline_execution("p2", [], False)
        c.record_pipeline_execution("p1", [], True)

        recent = c.get_recent_executions(pipeline_name="p1")
        assert len(recent) == 2
        assert all(ex.name == "p1" for ex in recent)

    def test_get_recent_executions_empty(self, tmp_collector):
        c, _ = tmp_collector
        assert c.get_recent_executions() == []

    def test_get_pipeline_statistics(self, tmp_collector):
        c, _ = tmp_collector
        c.record_pipeline_execution("p1", [], True)
        c.record_pipeline_execution("p2", [], False)

        stats = c.get_pipeline_statistics()
        assert "p1" in stats
        assert "p2" in stats
        assert stats["p1"]["successful"] == 1
        assert stats["p2"]["failed"] == 1

    def test_get_slowest_pipelines(self, tmp_collector):
        c, _ = tmp_collector
        c.record_pipeline_execution("slow-pipe", [{"duration": 10.0}], True)
        c.record_pipeline_execution("fast-pipe", [{"duration": 1.0}], True)

        slowest = c.get_slowest_pipelines(limit=2)
        assert len(slowest) == 2
        assert slowest[0]["name"] == "slow-pipe"

    def test_get_slowest_pipelines_empty(self, tmp_collector):
        c, _ = tmp_collector
        assert c.get_slowest_pipelines() == []

    def test_get_all_metrics_structure(self, tmp_collector):
        c, _ = tmp_collector
        c.record_pipeline_execution("p1", [{"duration": 1.5}], True)

        all_metrics = c.get_all_metrics()
        assert "pipeline" in all_metrics
        assert all_metrics["pipeline"]["total_executions"] == 1
        assert all_metrics["pipeline"]["completion_rate"] == 100.0
        assert "recent_executions" in all_metrics
        assert "slowest_pipelines" in all_metrics
        assert "timestamp" in all_metrics


# ============================================================================
# PipelineMetricsCollector — Reset
# ============================================================================


class TestCollectorReset:
    def test_reset_clears_metrics(self, tmp_collector):
        c, _ = tmp_collector
        c.record_pipeline_execution("p1", [], True)
        assert c.metrics.total_executions == 1

        c.reset_metrics()
        assert c.metrics.total_executions == 0
        assert c.metrics.successful_executions == 0
        assert c.metrics.recent_executions == []
        assert c.metrics.pipeline_stats == {}

    def test_reset_persists(self, tmp_collector):
        c, tmp = tmp_collector
        c.record_pipeline_execution("p1", [], True)
        c.reset_metrics()

        c2 = PipelineMetricsCollector(storage_path=tmp)
        assert c2.metrics.total_executions == 0


# ============================================================================
# Global convenience functions
# ============================================================================


class TestGlobalFunctions:
    def test_get_pipeline_collector_singleton(self):
        c1 = get_pipeline_collector()
        c2 = get_pipeline_collector()
        assert c1 is c2

    def test_record_execution(self, monkeypatch):
        calls = []

        class FakeCollector:
            def record_pipeline_execution(self, name, steps, completed):
                calls.append((name, steps, completed))

        monkeypatch.setattr("agora.metrics.collector._global_collector", FakeCollector())
        record_execution("p1", [{"duration": 1.0}], True)
        assert len(calls) == 1
        assert calls[0] == ("p1", [{"duration": 1.0}], True)

    def test_get_completion_rate(self, monkeypatch):
        class FakeCollector:
            def get_completion_rate(self, name):
                return 75.0 if name else 50.0

        monkeypatch.setattr("agora.metrics.collector._global_collector", FakeCollector())
        assert get_completion_rate("p1") == 75.0
        assert get_completion_rate() == 50.0

    def test_get_all_pipeline_metrics(self, monkeypatch):
        class FakeCollector:
            def get_all_metrics(self):
                return {"pipeline": {}, "timestamp": "now"}

        monkeypatch.setattr("agora.metrics.collector._global_collector", FakeCollector())
        result = get_all_pipeline_metrics()
        assert result["timestamp"] == "now"


# ============================================================================
# Edge cases
# ============================================================================


class TestEdgeCases:
    def test_pipeline_execution_no_steps(self, tmp_collector):
        c, _ = tmp_collector
        c.record_pipeline_execution("empty", [], True)
        assert c.metrics.total_duration == 0.0

    def test_get_slowest_pipelines_non_div_zero(self):
        """pipeline_stats with total=0 should not cause division by zero."""
        m = PipelineMetrics(pipeline_stats={"p1": {"total": 0, "successful": 0, "failed": 0, "total_duration": 0.0}})
        # This tests max(stats.get("total", 1), 1) guard in get_slowest_pipelines
        collector = PipelineMetricsCollector(storage_path=tempfile.mkdtemp())
        collector.metrics = m
        slowest = collector.get_slowest_pipelines()
        assert len(slowest) == 1
        assert slowest[0]["average_duration"] == 0.0
        assert slowest[0]["completion_rate"] == 0.0

    def test_exceed_1000_executions_does_not_grow_infinitely(self, tmp_collector):
        """The collector should cap recent_executions at 1000."""
        c, _ = tmp_collector
        for i in range(1005):
            c.record_pipeline_execution(f"p{i}", [], True)
        assert len(c.metrics.recent_executions) <= 1000

    def test_get_all_metrics_no_executions(self, tmp_collector):
        c, _ = tmp_collector
        all_m = c.get_all_metrics()
        assert all_m["pipeline"]["total_executions"] == 0
        assert all_m["slowest_pipelines"] == []
        assert all_m["recent_executions"] == []

    def test_save_metrics_failure_logged(self, tmp_collector, monkeypatch):
        """_save_metrics should catch and log exceptions gracefully."""
        c, _ = tmp_collector

        def _bad_open(*args, **kwargs):
            raise OSError("disk full")

        monkeypatch.setattr("builtins.open", _bad_open)
        # Should not raise — exception is caught and logged
        c.record_pipeline_execution("p1", [], True)
