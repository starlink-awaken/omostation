"""OMO 自愈代谢引擎单元测试。"""

import asyncio
import json
import time

import pytest

from omo.omo_self_healing import (
    DEFAULT_RULES,
    ErrorEventCounter,
    HealingRule,
    SelfHealingEngine,
    _severity_weight,
    get_healing_engine,
)


# ═══════════════════════════════════════════════════════════════════════════
# ErrorEventCounter
# ═══════════════════════════════════════════════════════════════════════════


class TestErrorEventCounter:
    def test_records_and_counts(self):
        counter = ErrorEventCounter(window_seconds=60)
        counter.record("SYSTEM_ERROR")
        counter.record("SYSTEM_ERROR")
        counter.record("TIMEOUT")
        assert counter.count() == 3
        assert counter.count("SYSTEM_ERROR") == 2
        assert counter.count("TIMEOUT") == 1
        assert counter.count("UNKNOWN") == 0

    def test_by_type(self):
        counter = ErrorEventCounter()
        counter.record("TYPE_A")
        counter.record("TYPE_A")
        counter.record("TYPE_B")
        by_type = counter.by_type()
        assert by_type == {"TYPE_A": 2, "TYPE_B": 1}

    def test_reset_clears_all(self):
        counter = ErrorEventCounter()
        counter.record("TEST")
        counter.reset()
        assert counter.count() == 0

    def test_expiry_removes_old_events(self):
        counter = ErrorEventCounter(window_seconds=0)  # 立即过期
        counter.record("TEST")
        assert counter.count() == 0  # 模拟时间流逝后过期

    def test_empty_counter(self):
        counter = ErrorEventCounter()
        assert counter.count() == 0
        assert counter.by_type() == {}
        assert counter.count("ANY") == 0


# ═══════════════════════════════════════════════════════════════════════════
# HealingRule
# ═══════════════════════════════════════════════════════════════════════════


class TestHealingRule:
    def test_matches_specific_types(self):
        rule = HealingRule(
            name="test",
            event_types=["ERROR", "CRASH"],
            threshold=3,
        )
        assert rule.matches("ERROR") is True
        assert rule.matches("CRASH") is True
        assert rule.matches("INFO") is False

    def test_empty_event_types_matches_all(self):
        rule = HealingRule(name="catch_all", threshold=1)
        assert rule.matches("ANYTHING") is True
        assert rule.matches("") is True

    def test_cool_down_initial(self):
        rule = HealingRule(name="test", threshold=1)
        assert rule.is_cooled_down() is True

    def test_cool_down_after_trigger(self):
        rule = HealingRule(name="test", threshold=1, cooldown_seconds=3600)
        rule.mark_triggered()
        assert rule.is_cooled_down() is False

    def test_cool_down_zero(self):
        rule = HealingRule(name="test", threshold=1, cooldown_seconds=0)
        rule.mark_triggered()
        assert rule.is_cooled_down() is True

    def test_default_values(self):
        rule = HealingRule(name="default_test", threshold=3)
        assert rule.severity == "warning"
        assert rule.action == "debt"
        assert rule.cooldown_seconds == 600


# ═══════════════════════════════════════════════════════════════════════════
# SelfHealingEngine
# ═══════════════════════════════════════════════════════════════════════════


class TestSelfHealingEngine:
    def test_no_trigger_below_threshold(self):
        rules = [HealingRule(name="test", event_types=["ERROR"], threshold=5)]
        engine = SelfHealingEngine(rules=rules)
        event = {"type": "ERROR", "source": "test"}

        async def _run():
            for _ in range(3):
                actions = await engine.on_event(event)
                assert actions == []

        asyncio.run(_run())

    def test_trigger_above_threshold(self):
        rules = [HealingRule(name="test", event_types=["ERROR"], threshold=2, cooldown_seconds=0)]
        engine = SelfHealingEngine(rules=rules)
        event = {"type": "ERROR", "source": "test"}

        async def _run():
            await engine.on_event(event)
            actions = await engine.on_event(event)
            assert len(actions) > 0
            assert actions[0]["rule"] == "test"

        asyncio.run(_run())

    def test_cool_down_prevents_retrigger(self):
        rules = [HealingRule(name="test", event_types=["ERROR"], threshold=1, cooldown_seconds=3600)]
        engine = SelfHealingEngine(rules=rules)
        event = {"type": "ERROR"}

        async def _run():
            actions1 = await engine.on_event(event)
            actions2 = await engine.on_event(event)
            assert len(actions1) > 0
            assert actions2 == []

        asyncio.run(_run())

    def test_unmatched_event_type_ignored(self):
        rules = [HealingRule(name="test", event_types=["ERROR"], threshold=1)]
        engine = SelfHealingEngine(rules=rules)

        async def _run():
            actions = await engine.on_event({"type": "INFO"})
            assert actions == []

        asyncio.run(_run())

    def test_multiple_rules_can_trigger(self):
        rules = [
            HealingRule(name="r1", event_types=["ERROR"], threshold=1, cooldown_seconds=0),
            HealingRule(name="r2", event_types=["ERROR"], threshold=1, cooldown_seconds=0),
        ]
        engine = SelfHealingEngine(rules=rules)

        async def _run():
            actions = await engine.on_event({"type": "ERROR"})
            assert len(actions) >= 1

        asyncio.run(_run())

    def test_get_status(self):
        engine = SelfHealingEngine()
        status = engine.get_status()
        assert status["rules_configured"] == len(DEFAULT_RULES)
        assert status["total_triggers"] == 0
        assert "current_events" in status
        assert "events_by_type" in status

    def test_default_rules_loaded(self):
        engine = SelfHealingEngine()
        assert len(engine._rules) == len(DEFAULT_RULES)
        assert engine._rules[0].name == "error_spike_audit"

    def test_debt_action_creates_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr("omo.omo_self_healing.OMO_ROOT", tmp_path)
        monkeypatch.setattr("omo.omo_self_healing.DEBT_ITEMS_DIR", tmp_path / ".omo" / "debt" / "items")
        monkeypatch.setattr("omo.omo_self_healing.DEBT_REGISTRY", tmp_path / ".omo" / "debt" / "registry.yaml")

        (tmp_path / ".omo" / "debt").mkdir(parents=True)
        (tmp_path / ".omo" / "debt" / "registry.yaml").write_text("seed_items: []\n")

        rules = [HealingRule(name="test", event_types=["ERR"], threshold=1, cooldown_seconds=0, action="debt")]
        engine = SelfHealingEngine(rules=rules, window_seconds=60)

        async def _run():
            await engine.on_event({"type": "ERR"})

        asyncio.run(_run())
        items = list((tmp_path / ".omo" / "debt" / "items").glob("auto-*.yaml"))
        assert len(items) > 0


# ═══════════════════════════════════════════════════════════════════════════
# Utilities
# ═══════════════════════════════════════════════════════════════════════════


class TestUtilities:
    def test_severity_weights(self):
        assert _severity_weight("critical") == 10.0
        assert _severity_weight("high") == 7.0
        assert _severity_weight("warning") == 4.0
        assert _severity_weight("info") == 2.0
        assert _severity_weight("unknown") == 4.0  # default

    def test_get_healing_engine_singleton(self):
        e1 = get_healing_engine()
        e2 = get_healing_engine()
        assert e1 is e2


# ═══════════════════════════════════════════════════════════════════════════
# Default Rules Validation
# ═══════════════════════════════════════════════════════════════════════════


class TestDefaultRules:
    def test_all_rules_have_valid_config(self):
        for rule in DEFAULT_RULES:
            assert rule.name
            assert rule.threshold > 0
            assert rule.severity in ("info", "warning", "high", "critical")
            assert rule.action in ("debt", "workflow", "fix", "both")
            assert rule.description

    def test_error_spike_rule_exists(self):
        names = [r.name for r in DEFAULT_RULES]
        assert "error_spike_audit" in names
        assert "timeout_cascade" in names

    def test_disk_quota_threshold_is_one(self):
        rule = next(r for r in DEFAULT_RULES if r.name == "disk_quota_warning")
        assert rule.threshold == 1
        assert rule.severity == "critical"

    def test_timeout_has_fix_scripts(self):
        rule = next(r for r in DEFAULT_RULES if r.name == "timeout_cascade")
        assert "restart_agora" in rule.fix_names

    def test_disk_quota_has_fix_scripts(self):
        rule = next(r for r in DEFAULT_RULES if r.name == "disk_quota_warning")
        assert len(rule.fix_names) >= 3

    def test_new_rules_exist(self):
        names = [r.name for r in DEFAULT_RULES]
        assert "memory_pressure" in names
        assert "process_dead_alert" in names

    def test_7_default_rules(self):
        assert len(DEFAULT_RULES) == 7


# ═══════════════════════════════════════════════════════════════════════════
# Fix Scripts
# ═══════════════════════════════════════════════════════════════════════════


class TestFixScripts:
    def test_fix_registry_has_all(self):
        from omo.omo_self_healing_fixes import FIX_REGISTRY, list_fixes

        fixes = list_fixes()
        assert len(fixes) == 6
        assert "clear_pytest_cache" in fixes
        assert "restart_agora" in fixes
        assert "disk_check" in fixes
        assert "process_health_check" in fixes

    def test_run_fix_disk_check(self):
        from omo.omo_self_healing_fixes import run_fix

        result = run_fix("disk_check")
        assert result["fix_name"] == "disk_check"
        assert "success" in result
        assert "output" in result

    def test_run_fix_unknown(self):
        from omo.omo_self_healing_fixes import run_fix

        result = run_fix("nonexistent_fix")
        assert result["success"] is False
        assert "Unknown fix" in result["output"]

    def test_run_fix_git_gc(self):
        from omo.omo_self_healing_fixes import run_fix

        result = run_fix("git_gc")
        assert result["fix_name"] == "git_gc"

    def test_run_fix_clean_temp(self):
        from omo.omo_self_healing_fixes import run_fix

        result = run_fix("clean_temp_files")
        assert result["fix_name"] == "clean_temp_files"
        assert result["success"] is True


# ═══════════════════════════════════════════════════════════════════════════
# Extended Engine Features
# ═══════════════════════════════════════════════════════════════════════════


class TestExtendedEngine:
    def test_fix_rules_exist(self):
        engine = SelfHealingEngine()
        fix_rules = [r for r in engine._rules if r.fix_names]
        assert len(fix_rules) >= 3  # timeout/disk/memory/process

    def test_status_includes_fixes(self):
        engine = SelfHealingEngine()
        status = engine.get_status()
        assert "fixes_executed" in status
        assert "recent_fixes" in status
        assert status["fixes_executed"] == 0

    def test_engine_has_publish_setting(self):
        engine = SelfHealingEngine()
        rule = next(r for r in engine._rules if r.name == "disk_quota_warning")
        assert rule.publish_event is False  # disk_quota 不发布事件

    def test_engine_event_url_configured(self):
        engine = SelfHealingEngine(agora_event_url="http://test:9999/events")
        assert engine._agora_event_url == "http://test:9999/events"
