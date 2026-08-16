# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false
"""Tests for sophia.learner — 范式学习循环 (ParadigmLearner).

补 learner 零测试债 (功能维度优化, sophia v1.0 测试补全).
用 tmp_path fixture 隔离 trace 目录, 避免污染真实 ~/sophia/traces."""

from sophia.learner import ParadigmLearner, ResearchTrace


def test_research_trace_defaults():
    t = ResearchTrace(query="q", paradigm_name="p", operations=["search"])
    assert t.transitions_fired == []
    assert t.transitions_failed == []
    assert t.completed is False
    assert t.quality_score == 0
    assert t.source_count == 0
    assert t.timestamp == ""


def test_learner_record_creates_file(tmp_path):
    learner = ParadigmLearner(trace_dir=str(tmp_path))
    trace = ResearchTrace(
        query="分析技术趋势",
        paradigm_name="analytical",
        operations=["search", "extract"],
        completed=True,
        quality_score=8,
    )
    learner.record(trace)
    files = list(tmp_path.glob("trace_*.json"))
    assert len(files) == 1
    # record 应填 timestamp
    assert trace.timestamp != ""


def test_learner_record_multiple(tmp_path):
    learner = ParadigmLearner(trace_dir=str(tmp_path))
    for i in range(5):
        learner.record(
            ResearchTrace(
                query=f"query-{i}",
                paradigm_name="analytical",
                operations=["search", "extract"],
                completed=True,
                quality_score=7,
                transitions_fired=["t1", "t2"],
            )
        )
    files = list(tmp_path.glob("trace_*.json"))
    assert len(files) == 5


def test_learner_get_effective_ops_empty(tmp_path):
    learner = ParadigmLearner(trace_dir=str(tmp_path))
    ops = learner.get_effective_ops()
    assert isinstance(ops, dict)


def test_learner_get_effective_ops_with_traces(tmp_path):
    learner = ParadigmLearner(trace_dir=str(tmp_path))
    for i in range(5):
        learner.record(
            ResearchTrace(
                query=f"q{i}",
                paradigm_name="analytical",
                operations=["search", "extract"],
                completed=True,
                quality_score=8,
                transitions_fired=["t1"],
            )
        )
    ops = learner.get_effective_ops(min_samples=2)
    assert isinstance(ops, dict)


def test_learner_suggest_ops_returns_list(tmp_path):
    learner = ParadigmLearner(trace_dir=str(tmp_path))
    suggestions = learner.suggest_ops(top_k=3)
    assert isinstance(suggestions, list)
    assert len(suggestions) <= 3


def test_learner_get_patterns_returns_list(tmp_path):
    learner = ParadigmLearner(trace_dir=str(tmp_path))
    patterns = learner.get_patterns()
    assert isinstance(patterns, list)


def test_learner_find_similar_traces_empty(tmp_path):
    learner = ParadigmLearner(trace_dir=str(tmp_path))
    similar = learner.find_similar_traces("test query", top_k=5)
    assert isinstance(similar, list)
