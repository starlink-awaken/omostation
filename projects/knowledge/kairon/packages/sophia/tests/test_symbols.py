"""Tests for sophia.symbols — 研究范式的符号系统"""
# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false

from sophia.symbols import (
    AtomicOp,
    ParadigmProgram,
    ResearchState,
    TransitionRule,
    gate_always,
)


def test_research_state_values():
    assert len(ResearchState) >= 10


def test_atomic_op_from_string():
    op = AtomicOp.from_string("search")
    assert op == AtomicOp.SEARCH
    assert AtomicOp.from_string("invalid") is None


def test_atomic_op_from_string_case_insensitive():
    op = AtomicOp.from_string("SEARCH")
    assert op == AtomicOp.SEARCH


def test_gate_always():
    assert gate_always({}) is True


def test_paradigm_program_validate_empty():
    prog = ParadigmProgram(name="test")
    issues = prog.validate()
    assert len(issues) > 0  # no ops, no transitions


def test_paradigm_program_validate_ok():
    fail_state = ResearchState.QUESTION
    prog = ParadigmProgram(
        name="test",
        operations=[AtomicOp.SEARCH, AtomicOp.SYNTHESIZE],
        transitions=[
            TransitionRule(ResearchState.QUESTION, AtomicOp.SEARCH, ResearchState.SEARCHING, gate_always, fail_state),
            TransitionRule(
                ResearchState.SEARCHING, AtomicOp.SYNTHESIZE, ResearchState.CONCLUSION, gate_always, fail_state
            ),
        ],
    )
    issues = prog.validate()
    assert issues == []


def test_paradigm_program_state_count():
    prog = ParadigmProgram(
        name="test",
        operations=[AtomicOp.SEARCH, AtomicOp.SYNTHESIZE],
        transitions=[
            TransitionRule(
                ResearchState.QUESTION, AtomicOp.SEARCH, ResearchState.SEARCHING, gate_always, ResearchState.QUESTION
            ),
            TransitionRule(
                ResearchState.SEARCHING,
                AtomicOp.SYNTHESIZE,
                ResearchState.CONCLUSION,
                gate_always,
                ResearchState.QUESTION,
            ),
        ],
    )
    assert prog.state_count == 3  # QUESTION, SEARCHING, CONCLUSION


def test_paradigm_program_to_dict():
    prog = ParadigmProgram(
        name="test",
        operations=[AtomicOp.SEARCH],
        transitions=[
            TransitionRule(
                ResearchState.QUESTION, AtomicOp.SEARCH, ResearchState.CONCLUSION, gate_always, ResearchState.QUESTION
            ),
        ],
    )
    d = prog.to_dict(include_query="test query")
    assert d["name"] == "test"
    assert "mermaid" in d


def test_paradigm_program_mermaid():
    prog = ParadigmProgram(
        name="test",
        operations=[AtomicOp.SEARCH],
        transitions=[
            TransitionRule(
                ResearchState.QUESTION, AtomicOp.SEARCH, ResearchState.CONCLUSION, gate_always, ResearchState.QUESTION
            ),
        ],
    )
    m = prog.to_mermaid()
    assert "stateDiagram" in m
