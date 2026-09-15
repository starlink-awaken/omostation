"""E2E tests for L0-L2 pipeline levels with real (but mocked) execution."""

import os
import shutil
from unittest.mock import AsyncMock, MagicMock

import pytest

try:
    from tests._helpers import _has_module
except ImportError:
    try:
        from .._helpers import _has_module
    except ImportError:

        def _has_module(name: str) -> bool:
            return True


class TestPipelineLevels:
    """Verify all pipeline levels can be constructed and executed."""

    def _make_mock_llm(self):
        llm = AsyncMock()
        llm.generate.return_value = "Mocked response with analysis and findings."
        return llm

    def _make_mock_search(self):
        from minerva.search.engine import SearchResult

        search = MagicMock()
        search.search = AsyncMock(
            return_value=[
                SearchResult(
                    title="Source A",
                    url="http://a.com",
                    snippet="Content A",
                    source="scholar",
                    rank_score=0.9,
                ),
                SearchResult(
                    title="Source B",
                    url="http://b.com",
                    snippet="Content B",
                    source="arxiv",
                    rank_score=0.8,
                ),
                SearchResult(
                    title="Source C",
                    url="http://c.com",
                    snippet="Content C",
                    source="web",
                    rank_score=0.7,
                ),
                SearchResult(
                    title="Source D",
                    url="http://d.com",
                    snippet="Content D",
                    source="ddg",
                    rank_score=0.6,
                ),
                SearchResult(
                    title="Source E",
                    url="http://e.com",
                    snippet="Content E",
                    source="metaso",
                    rank_score=0.5,
                ),
            ]
        )
        search.extract_content = AsyncMock(return_value="Full extracted content for analysis.")
        search.search_backend = AsyncMock(return_value=[])
        return search

    def _make_mock_nlp(self):
        nlp = MagicMock()
        ent1 = MagicMock()
        ent1.label_ = "ORG"
        ent1.text = "OpenAI"
        ent2 = MagicMock()
        ent2.label_ = "PERSON"
        ent2.text = "Sam Altman"
        doc = MagicMock()
        doc.ents = [ent1, ent2]
        nlp.return_value = doc
        return nlp

    @pytest.mark.skipif(not os.environ.get("OPENAI_API_KEY"), reason="requires LLM API key")
    @pytest.mark.asyncio
    async def test_l0_pipeline_runs(self):
        """L0: Search → QualityGate → Output — should complete <60s."""
        from minerva.knowledge.store import SQLiteKnowledgeStore
        from minerva.pipeline.engine import create_default_pipeline
        from minerva.triage.router import ResearchLevel, TriageResult

        llm = self._make_mock_llm()
        search = self._make_mock_search()
        kb = SQLiteKnowledgeStore(db_path=":memory:")
        pipeline = create_default_pipeline(llm, search, None, kb)

        triage = TriageResult(
            level=ResearchLevel.L0,
            scores={},
            cost_estimate=0,
            model_plan={},
            search_plan=[],
            warnings=[],
            total_score=0,
        )
        ctx = await pipeline.run("Test L0 query", ResearchLevel.L0, triage)

        assert ctx.report is not None, "L0 should produce a report"
        assert len(ctx.search_results) >= 1, "L0 should have search results"
        assert ctx.report_path is not None
        assert "search" in ctx.stage_timings

    @pytest.mark.skipif(not os.environ.get("OPENAI_API_KEY"), reason="requires LLM API key")
    @pytest.mark.asyncio
    async def test_l1_pipeline_runs(self):
        """L1: Decompose → Search → CrossAnalyze → Output."""
        from minerva.knowledge.store import SQLiteKnowledgeStore
        from minerva.pipeline.engine import create_default_pipeline
        from minerva.triage.router import ResearchLevel, TriageResult

        llm = self._make_mock_llm()
        search = self._make_mock_search()
        kb = SQLiteKnowledgeStore(db_path=":memory:")
        pipeline = create_default_pipeline(llm, search, None, kb)

        triage = TriageResult(
            level=ResearchLevel.L1,
            scores={},
            cost_estimate=0,
            model_plan={},
            search_plan=[],
            warnings=[],
            total_score=0,
        )
        ctx = await pipeline.run("Test L1 query", ResearchLevel.L1, triage)

        assert ctx.report is not None, "L1 should produce a report"
        assert len(ctx.sub_questions) >= 1, "L1 should have sub-questions"
        assert ctx.stage_timings

    @pytest.mark.skipif(not os.environ.get("OPENAI_API_KEY"), reason="requires LLM API key")
    @pytest.mark.asyncio
    async def test_l2_pipeline_runs(self):
        """L2: Decompose → Search → EntityExtract → DeepRead → CrossAnalyze → QualityGate → Output."""
        from minerva.knowledge.store import SQLiteKnowledgeStore
        from minerva.pipeline.engine import create_default_pipeline
        from minerva.triage.router import ResearchLevel, TriageResult

        llm = self._make_mock_llm()
        search = self._make_mock_search()
        nlp = self._make_mock_nlp()
        kb = SQLiteKnowledgeStore(db_path=":memory:")
        pipeline = create_default_pipeline(llm, search, nlp, kb)

        triage = TriageResult(
            level=ResearchLevel.L2,
            scores={},
            cost_estimate=0.3,
            model_plan={},
            search_plan=[],
            warnings=[],
            total_score=0,
        )
        ctx = await pipeline.run("Test L2 query", ResearchLevel.L2, triage)

        assert ctx.report is not None, "L2 should produce a report"
        assert len(ctx.entities) >= 1, "L2 should extract entities"
        assert len(ctx.sub_questions) >= 1, "L2 should have sub-questions"
        assert ctx.stage_timings

    @pytest.mark.skipif(not os.environ.get("OPENAI_API_KEY"), reason="requires LLM API key")
    @pytest.mark.asyncio
    async def test_l3_pipeline_runs(self):
        """L3: L2 stages + CounterArgument."""
        from minerva.knowledge.store import SQLiteKnowledgeStore
        from minerva.pipeline.engine import create_default_pipeline
        from minerva.triage.router import ResearchLevel, TriageResult

        llm = self._make_mock_llm()
        search = self._make_mock_search()
        nlp = self._make_mock_nlp()
        kb = SQLiteKnowledgeStore(db_path=":memory:")
        pipeline = create_default_pipeline(llm, search, nlp, kb)

        triage = TriageResult(
            level=ResearchLevel.L3,
            scores={},
            cost_estimate=2.0,
            model_plan={},
            search_plan=[],
            warnings=[],
            total_score=0,
        )
        ctx = await pipeline.run("Test L3 query", ResearchLevel.L3, triage)

        assert ctx.report is not None, "L3 should produce a report"
        assert ctx.stage_timings
        # L3 should have counter_argument in relations
        has_ca = any("counter_argument" in r for r in (ctx.relations or []))
        assert has_ca, "L3 should produce counter-arguments"

    @pytest.mark.skipif(not os.environ.get("OPENAI_API_KEY"), reason="requires LLM API key")
    @pytest.mark.asyncio
    async def test_l4_pipeline_runs(self):
        """L4: L3 stages + MultiModelVoting + ExtendedOutput."""
        from minerva.knowledge.store import SQLiteKnowledgeStore
        from minerva.pipeline.engine import create_default_pipeline
        from minerva.triage.router import ResearchLevel, TriageResult

        llm = self._make_mock_llm()
        search = self._make_mock_search()
        nlp = self._make_mock_nlp()
        kb = SQLiteKnowledgeStore(db_path=":memory:")
        pipeline = create_default_pipeline(llm, search, nlp, kb)

        triage = TriageResult(
            level=ResearchLevel.L4,
            scores={},
            cost_estimate=5.0,
            model_plan={},
            search_plan=[],
            warnings=[],
            total_score=0,
        )
        ctx = await pipeline.run("Test L4 query", ResearchLevel.L4, triage)

        assert ctx.report is not None, "L4 should produce a report"
        assert ctx.stage_timings
        # L4 should have voting
        has_voting = any("voting" in r for r in (ctx.relations or []))
        assert has_voting, "L4 should produce multi-model voting"

    @pytest.mark.skipif(not os.environ.get("OPENAI_API_KEY"), reason="requires LLM API key")
    @pytest.mark.asyncio
    async def test_paradigm_flow(self):
        """Verify Sophia paradigm compilation works within Minerva context."""
        from minerva.knowledge.store import SQLiteKnowledgeStore
        from minerva.pipeline.engine import create_default_pipeline
        from minerva.triage.router import ResearchLevel, TriageResult
        from sophia import compile_paradigm_sync

        prog = compile_paradigm_sync("Compare Python vs Go for backend")
        assert prog.validate() == []

        llm = self._make_mock_llm()
        search = self._make_mock_search()
        kb = SQLiteKnowledgeStore(db_path=":memory:")
        pipeline = create_default_pipeline(llm, search, None, kb)
        triage = TriageResult(
            level=ResearchLevel.L2,
            scores={},
            cost_estimate=0.3,
            model_plan={},
            search_plan=[],
            warnings=[],
            total_score=0,
        )
        ctx = await pipeline.run("Compare Python vs Go for backend", ResearchLevel.L2, triage)
        assert ctx.report is not None


class TestSophiaE2E:
    """End-to-end Sophia integration tests within Minerva context."""

    @pytest.mark.skipif(not _has_module("sophia"), reason="requires sophia Python package")
    def test_compile_roundtrip(self):
        from sophia import compile_paradigm_sync

        prog = compile_paradigm_sync("Compare Rust vs Go")
        d = prog.to_dict(include_query="Compare Rust vs Go")
        from sophia.compiler import recompile_from_dict

        p2 = recompile_from_dict(d)
        assert p2.name == prog.name
        assert len(p2.operations) == len(prog.operations)
        assert p2.validate() == []

    @pytest.mark.skipif(not _has_module("sophia"), reason="requires sophia Python package")
    def test_mermaid_export(self):
        from sophia import compile_paradigm_sync

        prog = compile_paradigm_sync("Survey AI trends")
        m = prog.to_mermaid()
        assert "stateDiagram" in m
        assert "conclusion" in m

    @pytest.mark.skipif(not _has_module("sophia"), reason="requires sophia Python package")
    def test_diff_and_validate(self):
        from sophia import compile_paradigm_sync

        p1 = compile_paradigm_sync("Compare A vs B")
        p2 = compile_paradigm_sync("Why does X fail?")
        delta = p1.diff(p2)
        assert delta["added_ops"] or delta["removed_ops"]
        assert p1.validate() == []
        assert p2.validate() == []

    @pytest.mark.skipif(not _has_module("sophia"), reason="requires sophia Python package")
    def test_empty_query_guards(self):
        import pytest
        from sophia import compile_paradigm_sync

        with pytest.raises(ValueError):
            compile_paradigm_sync("")
        with pytest.raises(ValueError):
            compile_paradigm_sync("   ")

    @pytest.mark.skipif(not _has_module("sophia"), reason="requires sophia Python package")
    def test_learner_record_and_retrieve(self):
        import tempfile

        from sophia import ParadigmLearner, ResearchTrace

        tmp = tempfile.mkdtemp()
        try:
            learner = ParadigmLearner(trace_dir=tmp)
            learner.record(
                ResearchTrace(
                    query="Test",
                    paradigm_name="Adaptive",
                    operations=["decompose", "search"],
                    quality_score=85,
                )
            )
            traces = learner._load_traces(10)
            assert len(traces) == 1
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
