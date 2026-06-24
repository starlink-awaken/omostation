"""Tests for Symphony Protocol state machine and models."""

from __future__ import annotations

import pytest

from ecos.l0.symphony.models import (
    AgentCapability,
    AgentProfile,
    MatchResult,
    StageHistoryEntry,
    StageInvariant,
    StageOutput,
    StageTransition,
    SymphonyStage,
    TaskRequirement,
    TransitionCondition,
    TransitionResult,
    Trigger,
    TriggerResult,
    TriggerType,
)
from ecos.l0.symphony.state_machine import SymphonyStateMachine


# ── SymphonyStage enum ──


class TestSymphonyStage:
    def test_values(self):
        assert SymphonyStage.ANCHORING == "anchoring"
        assert SymphonyStage.SCAFFOLDING == "scaffolding"
        assert SymphonyStage.IMPLEMENTATION == "implementation"
        assert SymphonyStage.POLISHING == "polishing"
        assert SymphonyStage.COMPLETE == "complete"

    def test_order(self):
        stages = list(SymphonyStage)
        assert stages == [
            SymphonyStage.ANCHORING,
            SymphonyStage.SCAFFOLDING,
            SymphonyStage.IMPLEMENTATION,
            SymphonyStage.POLISHING,
            SymphonyStage.COMPLETE,
        ]


# ── StageTransition ──


class TestStageTransition:
    def test_valid_transition(self):
        t = StageTransition(SymphonyStage.ANCHORING, SymphonyStage.SCAFFOLDING)
        assert t.is_valid() is True

    def test_invalid_transition(self):
        t = StageTransition(SymphonyStage.ANCHORING, SymphonyStage.COMPLETE)
        assert t.is_valid() is False

    def test_complete_has_no_outgoing(self):
        t = StageTransition(SymphonyStage.COMPLETE, SymphonyStage.ANCHORING)
        assert t.is_valid() is False

    def test_all_valid_paths(self):
        valid = [
            (SymphonyStage.ANCHORING, SymphonyStage.SCAFFOLDING),
            (SymphonyStage.SCAFFOLDING, SymphonyStage.IMPLEMENTATION),
            (SymphonyStage.IMPLEMENTATION, SymphonyStage.POLISHING),
            (SymphonyStage.POLISHING, SymphonyStage.COMPLETE),
        ]
        for from_stage, to_stage in valid:
            assert StageTransition(from_stage, to_stage).is_valid()

    def test_all_invalid_paths(self):
        invalid = [
            (SymphonyStage.ANCHORING, SymphonyStage.IMPLEMENTATION),
            (SymphonyStage.ANCHORING, SymphonyStage.POLISHING),
            (SymphonyStage.ANCHORING, SymphonyStage.COMPLETE),
            (SymphonyStage.SCAFFOLDING, SymphonyStage.ANCHORING),
            (SymphonyStage.SCAFFOLDING, SymphonyStage.POLISHING),
            (SymphonyStage.SCAFFOLDING, SymphonyStage.COMPLETE),
            (SymphonyStage.IMPLEMENTATION, SymphonyStage.ANCHORING),
            (SymphonyStage.IMPLEMENTATION, SymphonyStage.SCAFFOLDING),
            (SymphonyStage.IMPLEMENTATION, SymphonyStage.COMPLETE),
            (SymphonyStage.POLISHING, SymphonyStage.ANCHORING),
            (SymphonyStage.POLISHING, SymphonyStage.SCAFFOLDING),
            (SymphonyStage.POLISHING, SymphonyStage.IMPLEMENTATION),
        ]
        for from_stage, to_stage in invalid:
            assert not StageTransition(from_stage, to_stage).is_valid()


# ── TransitionCondition ──


class TestTransitionCondition:
    def test_predicate_true(self):
        cond = TransitionCondition(
            name="test", predicate=lambda ctx: ctx.get("ok", False), threshold=1.0
        )
        assert cond.predicate({"ok": True}) is True

    def test_predicate_false(self):
        cond = TransitionCondition(
            name="test", predicate=lambda ctx: ctx.get("ok", False), threshold=1.0
        )
        assert cond.predicate({"ok": False}) is False

    def test_default_description(self):
        cond = TransitionCondition(name="test", predicate=lambda ctx: True)
        assert cond.description == ""


# ── TransitionResult ──


class TestTransitionResult:
    def test_success_result(self):
        r = TransitionResult(
            success=True,
            from_stage=SymphonyStage.ANCHORING,
            to_stage=SymphonyStage.SCAFFOLDING,
            conditions_met=["task_defined"],
            message="ok",
        )
        assert r.success is True
        assert r.from_stage == SymphonyStage.ANCHORING
        assert r.to_stage == SymphonyStage.SCAFFOLDING
        assert r.conditions_met == ["task_defined"]
        assert r.conditions_failed == []

    def test_failure_result(self):
        r = TransitionResult(
            success=False,
            from_stage=None,
            to_stage=SymphonyStage.ANCHORING,
            conditions_failed=["task_defined"],
            message="fail",
        )
        assert r.success is False
        assert r.from_stage is None


# ── StageHistoryEntry ──


class TestStageHistoryEntry:
    def test_default_entered_at(self):
        entry = StageHistoryEntry(stage=SymphonyStage.ANCHORING)
        assert entry.stage == SymphonyStage.ANCHORING
        assert entry.exited_at is None
        assert entry.output is None

    def test_with_output(self):
        output = StageOutput(stage=SymphonyStage.ANCHORING, artifacts=["plan.md"])
        entry = StageHistoryEntry(stage=SymphonyStage.ANCHORING, output=output)
        assert entry.output is not None
        assert entry.output.artifacts == ["plan.md"]


# ── StageInvariant ──


class TestStageInvariant:
    def test_default_predicate(self):
        inv = StageInvariant(name="test")
        assert inv.predicate({}) is True

    def test_custom_predicate(self):
        inv = StageInvariant(name="test", predicate=lambda ctx: ctx.get("x", 0) > 5)
        assert inv.predicate({"x": 10}) is True
        assert inv.predicate({"x": 3}) is False

    def test_default_violation_action(self):
        inv = StageInvariant(name="test")
        assert inv.violation_action == "WARN"


# ── StageOutput ──


class TestStageOutput:
    def test_defaults(self):
        o = StageOutput(stage=SymphonyStage.ANCHORING)
        assert o.artifacts == []
        assert o.metrics == {}

    def test_with_data(self):
        o = StageOutput(
            stage=SymphonyStage.COMPLETE,
            artifacts=["report.pdf"],
            metrics={"coverage": 0.95},
        )
        assert o.artifacts == ["report.pdf"]
        assert o.metrics["coverage"] == 0.95


# ── AgentCapability / AgentProfile / TaskRequirement / MatchResult ──


class TestAgentCapability:
    def test_frozen(self):
        c = AgentCapability(name="python", proficiency=0.9)
        assert c.name == "python"
        assert c.proficiency == 0.9
        with pytest.raises(AttributeError):
            c.name = "rust"  # type: ignore[misc]

    def test_default_tags(self):
        c = AgentCapability(name="python")
        assert c.tags == ()


class TestAgentProfile:
    def test_defaults(self):
        p = AgentProfile(agent_id="agent-1")
        assert p.capabilities == {}
        assert p.current_load == 0.0
        assert p.max_capacity == 10

    def test_with_capabilities(self):
        cap = AgentCapability(name="python")
        p = AgentProfile(
            agent_id="agent-1",
            capabilities={cap: 0.9},
            specialization="backend",
        )
        assert p.capabilities[cap] == 0.9
        assert p.specialization == "backend"


class TestTaskRequirement:
    def test_defaults(self):
        t = TaskRequirement(task_id="task-1")
        assert t.required_capabilities == set()
        assert t.complexity == 5
        assert t.priority == 5

    def test_with_capabilities(self):
        cap = AgentCapability(name="python")
        t = TaskRequirement(
            task_id="task-1",
            required_capabilities={cap},
            complexity=8,
            priority=1,
        )
        assert cap in t.required_capabilities
        assert t.complexity == 8


class TestMatchResult:
    def test_defaults(self):
        m = MatchResult(task_id="t1", agent_id="a1", score=0.85)
        assert m.score_breakdown == {}
        assert m.reasoning == ""

    def test_with_breakdown(self):
        m = MatchResult(
            task_id="t1",
            agent_id="a1",
            score=0.85,
            score_breakdown={"skill": 0.9, "load": 0.8},
            reasoning="good match",
        )
        assert m.score_breakdown["skill"] == 0.9
        assert m.reasoning == "good match"


# ── Trigger / TriggerResult ──


class TestTrigger:
    def test_defaults(self):
        t = Trigger(id="t1", name="test")
        assert t.trigger_type == TriggerType.CONDITION_MET
        assert t.priority == 50
        assert t.enabled is True

    def test_custom(self):
        t = Trigger(
            id="t1",
            name="test",
            trigger_type=TriggerType.MANUAL,
            priority=10,
            enabled=False,
        )
        assert t.trigger_type == TriggerType.MANUAL
        assert t.enabled is False


class TestTriggerResult:
    def test_triggered(self):
        r = TriggerResult(trigger_id="t1", triggered=True, message="fired")
        assert r.triggered is True
        assert r.action_result is None

    def test_not_triggered(self):
        r = TriggerResult(trigger_id="t1", triggered=False)
        assert r.triggered is False


# ── SymphonyStateMachine ──


class TestSymphonyStateMachine:
    def test_initial_state(self):
        sm = SymphonyStateMachine()
        assert sm.get_current_stage() is None
        assert sm.get_history() == []
        assert sm.get_stage_history() == []
        assert sm.is_complete() is False

    def test_initial_context(self):
        sm = SymphonyStateMachine(initial_context={"task": "build"})
        assert sm.get_context() == {"task": "build"}

    def test_get_valid_transitions_from_none(self):
        sm = SymphonyStateMachine()
        assert sm.get_valid_transitions() == [SymphonyStage.ANCHORING]

    def test_can_transition_none_to_anchoring(self):
        sm = SymphonyStateMachine(initial_context={"task": "build"})
        assert sm.can_transition(SymphonyStage.ANCHORING) is True

    def test_can_transition_none_to_anchoring_fails_without_task(self):
        sm = SymphonyStateMachine()
        assert sm.can_transition(SymphonyStage.ANCHORING) is False

    def test_transition_none_to_anchoring(self):
        sm = SymphonyStateMachine(initial_context={"task": "build"})
        result = sm.transition(SymphonyStage.ANCHORING)
        assert result.success is True
        assert result.to_stage == SymphonyStage.ANCHORING
        assert sm.get_current_stage() == SymphonyStage.ANCHORING
        assert len(sm.get_history()) == 1

    def test_transition_none_to_anchoring_fails(self):
        sm = SymphonyStateMachine()
        result = sm.transition(SymphonyStage.ANCHORING)
        assert result.success is False
        assert result.conditions_failed == ["task_defined"]
        assert sm.get_current_stage() is None

    def test_illegal_transition(self):
        sm = SymphonyStateMachine()
        result = sm.transition(SymphonyStage.COMPLETE)
        assert result.success is False
        assert "illegal transition" in result.message

    def test_full_pipeline(self):
        """Test the complete happy path: None → ANCHORING → SCAFFOLDING → IMPLEMENTATION → POLISHING → COMPLETE"""
        sm = SymphonyStateMachine(
            initial_context={
                "task": "build feature",
                "context_completeness": 0.98,
                "ambiguities": [],
                "truth_locked": True,
                "architecture": {"name": "microservices"},
                "contract_signed": True,
                "dependency_graph": {"services": ["api", "db"]},
                "code_completion_rate": 0.97,
                "code_coverage": 0.85,
                "critical_issues": 0,
                "tests_passed": True,
                "performance_score": 0.95,
                "self_review_score": 0.90,
            }
        )

        # None → ANCHORING
        r1 = sm.transition(SymphonyStage.ANCHORING)
        assert r1.success is True
        assert sm.get_current_stage() == SymphonyStage.ANCHORING

        # ANCHORING → SCAFFOLDING
        r2 = sm.transition(SymphonyStage.SCAFFOLDING)
        assert r2.success is True
        assert sm.get_current_stage() == SymphonyStage.SCAFFOLDING

        # SCAFFOLDING → IMPLEMENTATION
        r3 = sm.transition(SymphonyStage.IMPLEMENTATION)
        assert r3.success is True
        assert sm.get_current_stage() == SymphonyStage.IMPLEMENTATION

        # IMPLEMENTATION → POLISHING
        r4 = sm.transition(SymphonyStage.POLISHING)
        assert r4.success is True
        assert sm.get_current_stage() == SymphonyStage.POLISHING

        # POLISHING → COMPLETE
        r5 = sm.transition(SymphonyStage.COMPLETE)
        assert r5.success is True
        assert sm.get_current_stage() == SymphonyStage.COMPLETE
        assert sm.is_complete() is True

        # Verify all transitions recorded
        assert len(sm.get_history()) == 5
        assert len(sm.get_stage_history()) == 4  # COMPLETE hasn't exited yet

    def test_transition_fails_on_missing_condition(self):
        sm = SymphonyStateMachine(initial_context={"task": "build"})
        sm.transition(SymphonyStage.ANCHORING)

        # Missing context_completeness
        result = sm.transition(SymphonyStage.SCAFFOLDING)
        assert result.success is False
        assert "context_completeness" in result.conditions_failed

    def test_update_context(self):
        sm = SymphonyStateMachine()
        sm.update_context({"task": "new task"})
        assert sm.get_context()["task"] == "new task"

    def test_validate_invariants_no_stage(self):
        sm = SymphonyStateMachine()
        assert sm.validate_invariants() == []

    def test_validate_invariants_anchoring_pass(self):
        sm = SymphonyStateMachine(
            initial_context={
                "task": "build",
                "context_frozen": True,
                "truth_contradiction": False,
            }
        )
        sm.transition(SymphonyStage.ANCHORING)
        assert sm.validate_invariants() == []

    def test_validate_invariants_anchoring_fail(self):
        sm = SymphonyStateMachine(
            initial_context={"task": "build", "context_frozen": False}
        )
        sm.transition(SymphonyStage.ANCHORING)
        violated = sm.validate_invariants()
        assert "context_immutable" in violated

    def test_validate_invariants_scaffolding_pass(self):
        sm = SymphonyStateMachine(
            initial_context={
                "task": "build",
                "context_completeness": 0.98,
                "ambiguities": [],
                "truth_locked": True,
                "architecture_layers": 4,
            }
        )
        sm.transition(SymphonyStage.ANCHORING)
        sm.transition(SymphonyStage.SCAFFOLDING)
        assert sm.validate_invariants() == []

    def test_validate_invariants_scaffolding_warn(self):
        sm = SymphonyStateMachine(
            initial_context={
                "task": "build",
                "context_completeness": 0.98,
                "ambiguities": [],
                "truth_locked": True,
            }
        )
        sm.transition(SymphonyStage.ANCHORING)
        sm.transition(SymphonyStage.SCAFFOLDING)
        violated = sm.validate_invariants()
        assert "architecture_layered" in violated

    def test_validate_invariants_implementation_fail(self):
        sm = SymphonyStateMachine(
            initial_context={
                "task": "build",
                "context_completeness": 0.98,
                "ambiguities": [],
                "truth_locked": True,
                "architecture": {"name": "x"},
                "contract_signed": True,
                "dependency_graph": {"a": "b"},
                "agent_conflict": True,
            }
        )
        sm.transition(SymphonyStage.ANCHORING)
        sm.transition(SymphonyStage.SCAFFOLDING)
        sm.transition(SymphonyStage.IMPLEMENTATION)
        violated = sm.validate_invariants()
        assert "agent_isolation" in violated

    def test_set_stage_output(self):
        sm = SymphonyStateMachine(initial_context={"task": "build"})
        sm.transition(SymphonyStage.ANCHORING)
        output = StageOutput(
            stage=SymphonyStage.ANCHORING,
            artifacts=["context.md"],
            metrics={"completeness": 0.95},
        )
        sm.set_stage_output(output)
        # The current stage entry should have the output
        assert sm._current_stage_entry is not None
        assert sm._current_stage_entry.output is not None
        assert sm._current_stage_entry.output.artifacts == ["context.md"]

    def test_reset(self):
        sm = SymphonyStateMachine(initial_context={"task": "build"})
        sm.transition(SymphonyStage.ANCHORING)
        assert sm.get_current_stage() == SymphonyStage.ANCHORING

        sm.reset()
        assert sm.get_current_stage() is None
        assert sm.get_history() == []
        assert sm.get_context() == {}

    def test_reset_with_context(self):
        sm = SymphonyStateMachine(initial_context={"task": "build"})
        sm.transition(SymphonyStage.ANCHORING)
        sm.reset(initial_context={"task": "reset"})
        assert sm.get_context() == {"task": "reset"}

    def test_get_valid_transitions_from_anchoring(self):
        sm = SymphonyStateMachine(
            initial_context={
                "task": "build",
                "context_completeness": 0.98,
                "ambiguities": [],
                "truth_locked": True,
            }
        )
        sm.transition(SymphonyStage.ANCHORING)
        valid = sm.get_valid_transitions()
        assert SymphonyStage.SCAFFOLDING in valid
        assert len(valid) == 1

    def test_get_valid_transitions_from_complete(self):
        sm = SymphonyStateMachine(
            initial_context={
                "task": "build",
                "context_completeness": 0.98,
                "ambiguities": [],
                "truth_locked": True,
                "architecture": {"name": "x"},
                "contract_signed": True,
                "dependency_graph": {"a": "b"},
                "code_completion_rate": 0.97,
                "code_coverage": 0.85,
                "critical_issues": 0,
                "tests_passed": True,
                "performance_score": 0.95,
                "self_review_score": 0.90,
            }
        )
        sm.transition(SymphonyStage.ANCHORING)
        sm.transition(SymphonyStage.SCAFFOLDING)
        sm.transition(SymphonyStage.IMPLEMENTATION)
        sm.transition(SymphonyStage.POLISHING)
        sm.transition(SymphonyStage.COMPLETE)
        assert sm.get_valid_transitions() == []

    def test_context_isolation(self):
        """get_context() should return a copy, not the original."""
        sm = SymphonyStateMachine(initial_context={"task": "build"})
        ctx = sm.get_context()
        ctx["task"] = "hacked"
        assert sm.get_context()["task"] == "build"
