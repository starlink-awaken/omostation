"""
Tests for model_driven.toolchain.trigger_m0 — Trigger M0 运行时快照
"""

from model_driven.toolchain.trigger_m0 import (
    TriggerM0Manager,
    TriggerRuntimeSnapshot,
)


class TestTriggerRuntimeSnapshot:
    def test_default_values(self):
        snap = TriggerRuntimeSnapshot(trigger_id="test-1")
        assert snap.trigger_id == "test-1"
        assert snap.status == "unknown"
        assert snap.health_score == 100.0
        assert snap.consecutive_failures == 0
        assert snap.consecutive_successes == 0

    def test_to_dict(self):
        snap = TriggerRuntimeSnapshot(trigger_id="test-1", status="healthy")
        d = snap.to_dict()
        assert d["trigger_id"] == "test-1"
        assert d["status"] == "healthy"
        assert "health_score" in d


class TestTriggerM0Manager:
    def test_record_execution_first_success(self):
        m0 = TriggerM0Manager()
        snap = m0.record_execution("t-1", success=True)
        assert snap.status == "healthy"  # 首次成功即 healthy
        assert snap.consecutive_successes == 1
        assert snap.consecutive_failures == 0

    def test_record_execution_multiple_success(self):
        m0 = TriggerM0Manager()
        for _ in range(5):
            snap = m0.record_execution("t-1", success=True)
        assert snap.status == "healthy"
        assert snap.health_score == 100.0  # capped at 100

    def test_record_execution_failures_degrade(self):
        m0 = TriggerM0Manager()
        m0.record_execution("t-1", success=True)  # healthy
        for _ in range(3):
            snap = m0.record_execution("t-1", success=False)
        assert snap.status == "degraded"
        assert snap.health_score <= 60.0  # 100 - 3*20 = 40

    def test_record_execution_five_failures_stopped(self):
        m0 = TriggerM0Manager()
        m0.record_execution("t-1", success=True)  # healthy
        for _ in range(5):
            snap = m0.record_execution("t-1", success=False)
        assert snap.status == "stopped"

    def test_recovery_after_failures(self):
        m0 = TriggerM0Manager()
        m0.record_execution("t-1", success=True)  # healthy
        for _ in range(3):
            m0.record_execution("t-1", success=False)  # degraded (3 failures)
        # 恢复: 需要连续 3 次成功才能变回 healthy (status 变为 degraded 后需 3 次)
        for _ in range(3):
            snap = m0.record_execution("t-1", success=True)
        assert snap.status == "healthy"

    def test_load_nonexistent(self):
        import tempfile
        d = tempfile.mkdtemp()
        m0 = TriggerM0Manager(state_dir=d)
        assert not m0.load()

    def test_get_snapshot(self):
        m0 = TriggerM0Manager()
        m0.record_execution("t-1", success=True)
        snap = m0.get_snapshot("t-1")
        assert snap is not None
        assert snap.status == "healthy"
        assert m0.get_snapshot("nonexistent") is None

    def test_get_all_snapshots(self):
        m0 = TriggerM0Manager()
        m0.record_execution("t-1", success=True)
        m0.record_execution("t-2", success=False)
        all_snaps = m0.get_all_snapshots()
        assert len(all_snaps) == 2

    def test_save_and_load(self, tmp_path):
        m0 = TriggerM0Manager(state_dir=str(tmp_path))
        m0.record_execution("t-1", success=True, duration_seconds=2.5)
        assert m0.save()

        m0_2 = TriggerM0Manager(state_dir=str(tmp_path))
        assert m0_2.load()
        snap = m0_2.get_snapshot("t-1")
        assert snap is not None
        assert snap.status == "healthy"
        assert snap.last_duration_seconds == 2.5

    def test_load_nonexistent_v2(self):
        import tempfile
        d = tempfile.mkdtemp()
        m0 = TriggerM0Manager(state_dir=d)
        assert not m0.load()

    def test_detect_drift(self):
        m0 = TriggerM0Manager()
        m0.record_execution("t-1", success=False)
        m0.record_execution("t-1", success=False)
        m0.record_execution("t-1", success=False)  # degraded

        m1_triggers = [{"id": "t-1", "status": "active"}]
        drifts = m0.detect_drift(m1_triggers)
        assert len(drifts) == 1
        assert drifts[0]["severity"] == "high"
        assert drifts[0]["type"] == "status_drift"

    def test_detect_drift_missing_m0(self):
        m0 = TriggerM0Manager()
        m1_triggers = [{"id": "t-missing", "status": "active"}]
        drifts = m0.detect_drift(m1_triggers)
        assert len(drifts) == 1
        assert drifts[0]["severity"] == "warning"
        assert drifts[0]["type"] == "missing_m0_snapshot"

    def test_get_health_summary(self):
        m0 = TriggerM0Manager()
        m0.record_execution("t-1", success=True)
        m0.record_execution("t-2", success=True)
        for _ in range(3):
            m0.record_execution("t-3", success=False)
        summary = m0.get_health_summary()
        assert summary["total_triggers"] == 3
        assert summary["healthy"] == 2
        assert summary["degraded"] == 1
        assert summary["health_pct"] == 66.7

    def test_metadata(self):
        m0 = TriggerM0Manager()
        snap = m0.record_execution("t-1", success=True, metadata={"version": "1.0"})
        assert snap.metadata["version"] == "1.0"
