"""Tests for Symphony Protocol trigger engine."""

from __future__ import annotations

import asyncio

import pytest

from ecos.l0.symphony.models import (
    SymphonyStage,
    Trigger,
)
from ecos.l0.symphony.triggers import (
    TriggerEngine,
    create_default_triggers,
    setup_trigger_engine,
)


class FakeStageManager:
    """Minimal StageManager implementation for testing."""

    def __init__(self) -> None:
        self._context: dict = {}
        self.transitions: list[SymphonyStage] = []

    def transition_to(self, stage: SymphonyStage) -> None:
        self.transitions.append(stage)

    def get_context(self) -> dict:
        return self._context

    def set_context(self, ctx: dict) -> None:
        self._context = ctx


# ── TriggerEngine ──


class TestTriggerEngineInit:
    def test_default_init(self):
        engine = TriggerEngine()
        assert engine._stage_manager is None
        assert engine._triggers == {}
        assert engine._history == []
        assert engine._running is False
        assert engine._monitor_task is None

    def test_init_with_stage_manager(self):
        mgr = FakeStageManager()
        engine = TriggerEngine(stage_manager=mgr)
        assert engine._stage_manager is mgr


class TestTriggerEngineSetStageManager:
    def test_set_stage_manager(self):
        engine = TriggerEngine()
        mgr = FakeStageManager()
        engine.set_stage_manager(mgr)
        assert engine._stage_manager is mgr


class TestTriggerEngineRegister:
    def test_register_trigger(self):
        engine = TriggerEngine()
        trigger = Trigger(id="t1", name="test")
        engine.register_trigger(trigger)
        assert engine.get_trigger("t1") is trigger
        assert len(engine.get_all_triggers()) == 1

    def test_register_multiple(self):
        engine = TriggerEngine()
        engine.register_trigger(Trigger(id="t1", name="one"))
        engine.register_trigger(Trigger(id="t2", name="two"))
        assert len(engine.get_all_triggers()) == 2


class TestTriggerEngineUnregister:
    def test_unregister_existing(self):
        engine = TriggerEngine()
        engine.register_trigger(Trigger(id="t1", name="test"))
        engine.unregister_trigger("t1")
        assert engine.get_trigger("t1") is None

    def test_unregister_nonexistent(self):
        engine = TriggerEngine()
        engine.unregister_trigger("nonexistent")  # should not raise


class TestTriggerEngineEnableDisable:
    def test_enable_trigger(self):
        engine = TriggerEngine()
        t = Trigger(id="t1", name="test", enabled=False)
        engine.register_trigger(t)
        engine.enable_trigger("t1")
        assert t.enabled is True

    def test_disable_trigger(self):
        engine = TriggerEngine()
        t = Trigger(id="t1", name="test", enabled=True)
        engine.register_trigger(t)
        engine.disable_trigger("t1")
        assert t.enabled is False

    def test_enable_nonexistent(self):
        engine = TriggerEngine()
        engine.enable_trigger("nonexistent")  # should not raise

    def test_disable_nonexistent(self):
        engine = TriggerEngine()
        engine.disable_trigger("nonexistent")  # should not raise


class TestTriggerEngineEvaluate:
    def test_no_triggers(self):
        engine = TriggerEngine()
        results = engine.evaluate_and_trigger({"x": 1})
        assert results == []

    def test_trigger_condition_met(self):
        engine = TriggerEngine()
        action_log: list[str] = []

        def action() -> str:
            action_log.append("fired")
            return "done"

        t = Trigger(
            id="t1",
            name="test",
            condition=lambda ctx: ctx.get("x", 0) > 5,
            action=action,
        )
        engine.register_trigger(t)
        results = engine.evaluate_and_trigger({"x": 10})

        assert len(results) == 1
        assert results[0].triggered is True
        assert results[0].trigger_id == "t1"
        assert results[0].action_result == "done"
        assert action_log == ["fired"]

    def test_trigger_condition_not_met(self):
        engine = TriggerEngine()
        t = Trigger(
            id="t1",
            name="test",
            condition=lambda ctx: ctx.get("x", 0) > 5,
        )
        engine.register_trigger(t)
        results = engine.evaluate_and_trigger({"x": 1})

        assert len(results) == 1
        assert results[0].triggered is False
        assert results[0].trigger_id == "t1"

    def test_disabled_trigger_skipped(self):
        engine = TriggerEngine()
        t = Trigger(
            id="t1",
            name="test",
            condition=lambda ctx: True,
            enabled=False,
        )
        engine.register_trigger(t)
        results = engine.evaluate_and_trigger({})
        assert len(results) == 0

    def test_priority_order(self):
        engine = TriggerEngine()
        order: list[str] = []

        engine.register_trigger(
            Trigger(
                id="low",
                name="low",
                condition=lambda ctx: True,
                action=lambda: order.append("low"),
                priority=10,
            )
        )
        engine.register_trigger(
            Trigger(
                id="high",
                name="high",
                condition=lambda ctx: True,
                action=lambda: order.append("high"),
                priority=100,
            )
        )
        engine.evaluate_and_trigger({})
        # Higher priority first
        assert order == ["high", "low"]

    def test_trigger_exception_handled(self):
        engine = TriggerEngine()

        def failing_condition(ctx: dict) -> bool:
            msg = "oops"
            raise ValueError(msg)

        t = Trigger(
            id="t1",
            name="failing",
            condition=failing_condition,
        )
        engine.register_trigger(t)
        results = engine.evaluate_and_trigger({})

        assert len(results) == 1
        assert results[0].triggered is False
        assert "oops" in results[0].message

    def test_context_from_stage_manager(self):
        engine = TriggerEngine()
        mgr = FakeStageManager()
        mgr.set_context({"x": 42})
        engine.set_stage_manager(mgr)

        t = Trigger(
            id="t1",
            name="test",
            condition=lambda ctx: ctx.get("x") == 42,
        )
        engine.register_trigger(t)
        results = engine.evaluate_and_trigger()  # no context passed
        assert len(results) == 1
        assert results[0].triggered is True

    def test_context_from_stage_manager_empty_when_none(self):
        engine = TriggerEngine()
        results = engine.evaluate_and_trigger()  # no mgr, no context
        assert results == []


class TestTriggerEngineHistory:
    def test_history_recorded(self):
        engine = TriggerEngine()
        t = Trigger(
            id="t1",
            name="test",
            condition=lambda ctx: True,
        )
        engine.register_trigger(t)
        engine.evaluate_and_trigger({})

        history = engine.get_history()
        assert len(history) == 1
        assert history[0].trigger_id == "t1"

    def test_clear_history(self):
        engine = TriggerEngine()
        t = Trigger(id="t1", name="test", condition=lambda ctx: True)
        engine.register_trigger(t)
        engine.evaluate_and_trigger({})
        assert len(engine.get_history()) == 1
        engine.clear_history()
        assert engine.get_history() == []


class TestTriggerEngineGetStatus:
    def test_empty_status(self):
        engine = TriggerEngine()
        status = engine.get_status()
        assert status["total_triggers"] == 0
        assert status["enabled_triggers"] == 0
        assert status["disabled_triggers"] == 0
        assert status["is_running"] is False
        assert status["history_count"] == 0
        assert status["trigger_names"] == []

    def test_status_with_triggers(self):
        engine = TriggerEngine()
        engine.register_trigger(Trigger(id="t1", name="one", enabled=True))
        engine.register_trigger(Trigger(id="t2", name="two", enabled=False))
        engine.evaluate_and_trigger({})

        status = engine.get_status()
        assert status["total_triggers"] == 2
        assert status["enabled_triggers"] == 1
        assert status["disabled_triggers"] == 1
        assert status["history_count"] == 1
        assert "t1" in status["trigger_names"]


class TestTriggerEngineMonitoring:
    @pytest.mark.asyncio
    async def test_start_stop_monitoring(self):
        engine = TriggerEngine()
        mgr = FakeStageManager()
        mgr.set_context({"x": 1})
        engine.set_stage_manager(mgr)

        # Register a trigger that will fire
        engine.register_trigger(
            Trigger(
                id="t1",
                name="test",
                condition=lambda ctx: ctx.get("x", 0) > 0,
                action=lambda: None,
            )
        )

        task = await engine.start_monitoring_task(interval=0.05)
        assert engine._running is True

        # Let it run for a bit
        await asyncio.sleep(0.15)
        assert len(engine.get_history()) >= 1

        engine.stop_monitoring()
        assert engine._running is False

        # Wait for task to complete
        await asyncio.sleep(0.05)
        assert task.done() or task.cancelled()

    @pytest.mark.asyncio
    async def test_stop_monitoring_without_task(self):
        engine = TriggerEngine()
        engine.stop_monitoring()  # should not raise
        assert engine._running is False


# ── create_default_triggers ──


class TestCreateDefaultTriggers:
    def test_creates_four_triggers(self):
        mgr = FakeStageManager()
        triggers = create_default_triggers(mgr)
        assert len(triggers) == 4

    def test_trigger_ids(self):
        mgr = FakeStageManager()
        triggers = create_default_triggers(mgr)
        ids = [t.id for t in triggers]
        assert ids == [
            "anchoring_to_scaffolding",
            "scaffolding_to_implementation",
            "implementation_to_polishing",
            "polishing_to_complete",
        ]

    def test_all_have_priority_100(self):
        mgr = FakeStageManager()
        triggers = create_default_triggers(mgr)
        for t in triggers:
            assert t.priority == 100

    def test_anchoring_trigger_condition(self):
        mgr = FakeStageManager()
        triggers = create_default_triggers(mgr)
        t = triggers[0]

        # Conditions met
        assert (
            t.condition(
                {
                    "context_completeness": 0.98,
                    "ambiguities": [],
                    "truth_locked": True,
                }
            )
            is True
        )

        # Conditions not met
        assert (
            t.condition(
                {
                    "context_completeness": 0.50,
                    "ambiguities": [],
                    "truth_locked": True,
                }
            )
            is False
        )

    def test_scaffolding_trigger_condition(self):
        mgr = FakeStageManager()
        triggers = create_default_triggers(mgr)
        t = triggers[1]

        assert (
            t.condition(
                {
                    "architecture": {"name": "x"},
                    "contract_signed": True,
                    "dependency_graph": {"a": "b"},
                }
            )
            is True
        )

        assert (
            t.condition(
                {
                    "architecture": None,
                    "contract_signed": True,
                    "dependency_graph": {"a": "b"},
                }
            )
            is False
        )

    def test_implementation_trigger_condition(self):
        mgr = FakeStageManager()
        triggers = create_default_triggers(mgr)
        t = triggers[2]

        assert (
            t.condition(
                {
                    "code_completion_rate": 0.97,
                    "code_coverage": 0.85,
                    "critical_issues": 0,
                }
            )
            is True
        )

        assert (
            t.condition(
                {
                    "code_completion_rate": 0.50,
                    "code_coverage": 0.85,
                    "critical_issues": 0,
                }
            )
            is False
        )

    def test_polishing_trigger_condition(self):
        mgr = FakeStageManager()
        triggers = create_default_triggers(mgr)
        t = triggers[3]

        assert (
            t.condition(
                {
                    "tests_passed": True,
                    "performance_score": 0.95,
                    "self_review_score": 0.90,
                }
            )
            is True
        )

        assert (
            t.condition(
                {
                    "tests_passed": False,
                    "performance_score": 0.95,
                    "self_review_score": 0.90,
                }
            )
            is False
        )

    def test_triggers_call_transition(self):
        mgr = FakeStageManager()
        triggers = create_default_triggers(mgr)

        # Each trigger's action should call transition_to
        triggers[0].action()
        assert mgr.transitions == [SymphonyStage.SCAFFOLDING]

        triggers[1].action()
        assert mgr.transitions[-1] == SymphonyStage.IMPLEMENTATION

        triggers[2].action()
        assert mgr.transitions[-1] == SymphonyStage.POLISHING

        triggers[3].action()
        assert mgr.transitions[-1] == SymphonyStage.COMPLETE


# ── setup_trigger_engine ──


class TestSetupTriggerEngine:
    def test_setup_returns_engine(self):
        mgr = FakeStageManager()
        engine = setup_trigger_engine(mgr)
        assert isinstance(engine, TriggerEngine)
        assert engine._stage_manager is mgr

    def test_setup_registers_four_triggers(self):
        mgr = FakeStageManager()
        engine = setup_trigger_engine(mgr)
        assert len(engine.get_all_triggers()) == 4

    def test_setup_triggers_are_enabled(self):
        mgr = FakeStageManager()
        engine = setup_trigger_engine(mgr)
        for t in engine.get_all_triggers():
            assert t.enabled is True
