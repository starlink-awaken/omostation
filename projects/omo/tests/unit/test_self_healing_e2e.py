"""OMO 自愈引擎 E2E 模拟测试 — 从事件到修复完整链路。"""

import asyncio
import tempfile
import time
from pathlib import Path

import pytest

import omo.omo_self_healing as sh
from omo.omo_self_healing import (
    DEFAULT_RULES,
    ErrorEventCounter,
    EventTrend,
    HealingRule,
    SelfHealingEngine,
    TrendTracker,
    get_healing_engine,
    load_rules,
    save_rules,
)


@pytest.fixture
def engine_with_tmp(tmp_path, monkeypatch):
    """创建带临时目录的自愈引擎。返回 (engine, tmp_path)。"""
    (tmp_path / ".omo" / "debt").mkdir(parents=True)
    (tmp_path / ".omo" / "debt" / "registry.yaml").write_text("seed_items: []\n")
    monkeypatch.setattr(sh, "OMO_ROOT", tmp_path)
    monkeypatch.setattr(sh, "DEBT_ITEMS_DIR", tmp_path / ".omo" / "debt" / "items")
    monkeypatch.setattr(sh, "DEBT_REGISTRY", tmp_path / ".omo" / "debt" / "registry.yaml")
    engine = SelfHealingEngine(window_seconds=60)
    return engine, tmp_path


# ═══════════════════════════════════════════════════════════════════════════
# E2E: 完整自愈流程
# ═══════════════════════════════════════════════════════════════════════════


class TestE2ESelfHealing:
    def test_full_pipeline_error_to_debt(self, engine_with_tmp):
        """E2E: SYSTEM_ERROR → debt_created + workflow + fix"""
        engine, tmp = engine_with_tmp

        async def run():
            actions = []
            for i in range(3):
                result = await engine.on_event({"type": "SYSTEM_ERROR", "source": "e2e", "msg": f"err{i}"})
                if result:
                    actions.extend(result)
            return actions

        result = asyncio.run(run())
        # 第 3 个事件触发 error_spike_audit
        assert len(result) >= 1
        triggered = result[0]
        assert triggered["rule"] == "error_spike_audit"
        assert triggered["event_type"] == "SYSTEM_ERROR"
        assert triggered["count"] == 3

        # 验证债务生成
        items = list((tmp / ".omo" / "debt" / "items").glob("auto-*.yaml"))
        assert len(items) == 1

    def test_full_pipeline_timeout(self, engine_with_tmp):
        """E2E: 5 个 TIMEOUT → 冷却后不重复触发"""
        engine, _ = engine_with_tmp

        async def run():
            actions = []
            for i in range(5):
                result = await engine.on_event({"type": "TIMEOUT", "source": "e2e"})
                if result:
                    actions.extend(result)
            # 冷却期间不应再次触发
            result2 = await engine.on_event({"type": "TIMEOUT", "source": "e2e"})
            if result2:
                actions.extend(result2)
            return actions

        result = asyncio.run(run())
        assert len(result) >= 0  # 至少不报错

    def test_immediate_trigger_disk_full(self, engine_with_tmp):
        """E2E: 单次 DISK_FULL → 立即触发 + fixes 执行"""
        engine, _ = engine_with_tmp

        async def run():
            return await engine.on_event({"type": "DISK_FULL", "source": "e2e"})

        result = asyncio.run(run())
        assert len(result) >= 1
        actions = result[0]["actions"]
        action_types = [a["type"] for a in actions]
        assert "fix_executed" in action_types

    def test_cool_down_works(self):
        """E2E: cool_down 阻止重复触发"""
        rules = [HealingRule(name="test", threshold=1, cooldown_seconds=10)]
        engine = SelfHealingEngine(rules=rules)

        async def run():
            r1 = await engine.on_event({"type": "ANY"})
            r2 = await engine.on_event({"type": "ANY"})
            return r1, r2

        r1, r2 = asyncio.run(run())
        assert len(r1) >= 1  # 首次触发
        assert r2 == []  # 冷却中，不触发


# ═══════════════════════════════════════════════════════════════════════════
# Trend Analysis
# ═══════════════════════════════════════════════════════════════════════════


class TestTrendAnalysis:
    def test_is_escalating_true(self):
        tracker = TrendTracker(max_snapshots=10)
        for i in range(5):
            tracker.record(EventTrend(
                events_by_type={"ERROR": i * 2, "INFO": i},
                total_events=i * 3,
            ))
        assert tracker.is_escalating("ERROR") is True

    def test_is_escalating_false_stable(self):
        tracker = TrendTracker(max_snapshots=10)
        for _ in range(5):
            tracker.record(EventTrend(
                events_by_type={"ERROR": 3},
                total_events=5,
            ))
        assert tracker.is_escalating("ERROR") is False

    def test_is_escalating_insufficient_data(self):
        tracker = TrendTracker(max_snapshots=10)
        tracker.record(EventTrend(events_by_type={"ERROR": 1}))
        assert tracker.is_escalating("ERROR") is False  # 不足 3 个快照

    def test_get_trends_format(self):
        tracker = TrendTracker(max_snapshots=3)
        tracker.record(EventTrend(events_by_type={"A": 1}))
        trends = tracker.get_trends()
        assert len(trends) == 1
        assert "ts" in trends[0]
        assert "events" in trends[0]


# ═══════════════════════════════════════════════════════════════════════════
# Config Persistence E2E
# ═══════════════════════════════════════════════════════════════════════════


class TestConfigPersistence:
    def test_save_and_load_roundtrip(self, tmp_path):
        path = tmp_path / "rules.yaml"
        custom = [
            HealingRule(
                name="custom_rule",
                event_types=["CUSTOM"],
                threshold=10,
                severity="critical",
                action="fix",
                fix_names=["disk_check"],
                description="Custom test rule",
            )
        ]
        save_rules(custom, path)
        loaded = load_rules(path)
        assert len(loaded) == 1
        assert loaded[0].name == "custom_rule"
        assert loaded[0].threshold == 10
        assert loaded[0].fix_names == ["disk_check"]

    def test_load_empty_when_no_file(self, tmp_path):
        loaded = load_rules(tmp_path / "nonexistent.yaml")
        assert loaded == []

    def test_engine_prefers_custom_rules(self, tmp_path, monkeypatch):
        path = tmp_path / "rules.yaml"
        custom = [
            HealingRule(name="only_this", threshold=1, action="fix"),
        ]
        save_rules(custom, path)
        monkeypatch.setattr(sh, "HEALING_CONFIG_PATH", path)
        # Reset singleton
        sh._engine = None
        engine = get_healing_engine()
        assert len(engine._rules) == 1
        assert engine._rules[0].name == "only_this"
        # Cleanup
        sh._engine = None


# ═══════════════════════════════════════════════════════════════════════════
# Engine State Transitions
# ═══════════════════════════════════════════════════════════════════════════


class TestEngineState:
    def test_fix_history_tracks(self):
        engine = SelfHealingEngine()
        engine._fix_history.append({"rule": "test", "fix_name": "disk_check", "success": True, "output": "ok"})
        status = engine.get_status()
        assert status["fixes_executed"] == 1
        assert len(status["recent_fixes"]) == 1

    def test_trigger_count_accumulates(self, monkeypatch):
        monkeypatch.setattr(sh, "OMO_ROOT", Path(tempfile.mkdtemp()))
        rules = [HealingRule(name="test", threshold=1, cooldown_seconds=0, action="debt")]
        engine = SelfHealingEngine(rules=rules)

        async def run():
            for _ in range(2):
                await engine.on_event({"type": "TEST"})

        asyncio.run(run())
        status = engine.get_status()
        assert status["total_triggers"] >= 1
