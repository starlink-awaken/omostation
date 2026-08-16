"""Unit tests for all pipeline stage implementations in minerva.pipeline.stages."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from minerva.pipeline.engine import QualityGateError, ResearchContext
from minerva.triage.router import ResearchLevel, TriageResult

# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


def _make_triage(level: ResearchLevel = ResearchLevel.L2) -> TriageResult:
    """Create a minimal TriageResult for testing."""
    return TriageResult(
        level=level,
        scores={
            "domain_complexity": 3,
            "timeliness": 2,
            "depth_required": 4,
            "multi_source": 3,
            "privacy_sensitivity": 1,
        },
        cost_estimate=0.30,
        model_plan={"reasoner": "local"},
        search_plan=["web_search"],
    )


def _make_ctx(
    query: str = "test query",
    level: ResearchLevel = ResearchLevel.L2,
    search_results: list[dict] | None = None,
    entities: list[dict] | None = None,
    contradictions: list[dict] | None = None,
    relations: list[dict] | None = None,
    sub_questions: list[str] | None = None,
    cost: float = 0.0,
) -> ResearchContext:
    """Create a ResearchContext with optional pre-populated fields."""
    return ResearchContext(
        query=query,
        level=level,
        triage=_make_triage(level),
        search_results=search_results or [],
        entities=entities or [],
        contradictions=contradictions or [],
        relations=relations or [],
        sub_questions=sub_questions or [],
        cost=cost,
    )


def _make_search_result(
    title: str = "Test Result",
    url: str = "https://example.com",
    snippet: str = "A test snippet.",
    source: str = "web",
    published_date: str = "2024-01-01",
    rank_score: float = 0.9,
    content: str | None = None,
) -> dict:
    """Create a search result dict matching the shape produced by search stages."""
    result = {
        "title": title,
        "url": url,
        "snippet": snippet,
        "source": source,
        "published_date": published_date,
        "rank_score": rank_score,
    }
    if content is not None:
        result["content"] = content
    return result


def _make_spacy_ent(label: str, text: str) -> MagicMock:
    """Create a MagicMock that behaves like a spaCy Span entity."""
    ent = MagicMock()
    ent.label_ = label
    ent.text = text
    return ent


def _make_spacy_doc(*ents: MagicMock) -> MagicMock:
    """Create a MagicMock that behaves like a spaCy Doc with given entities."""
    doc = MagicMock()
    doc.ents = list(ents)
    return doc


# ===================================================================
# DecomposeStageImpl
# ===================================================================


class TestDecomposeStageImpl:
    """Tests for DecomposeStageImpl — query decomposition into sub-questions."""

    @pytest.mark.asyncio
    async def test_decomposes_query_into_sub_questions(self):
        """Decompose should parse LLM response lines into ctx.sub_questions."""
        from minerva.pipeline.stages import DecomposeStageImpl

        llm = AsyncMock()
        llm.generate.return_value = "What is the first aspect?\nWhat is the second aspect?\nThird sub question here.\n"

        stage = DecomposeStageImpl(llm=llm)
        ctx = _make_ctx(query="What is MoE?")

        result = await stage.execute(ctx)

        assert len(result.sub_questions) == 3
        assert "What is the first aspect?" in result.sub_questions
        assert "What is the second aspect?" in result.sub_questions
        assert "Third sub question here." in result.sub_questions

    @pytest.mark.asyncio
    async def test_falls_back_to_original_query_on_exception(self):
        """On LLM failure, exception should propagate."""
        from minerva.pipeline.stages import DecomposeStageImpl

        llm = AsyncMock()
        llm.generate.side_effect = RuntimeError("LLM unavailable")

        stage = DecomposeStageImpl(llm=llm)
        ctx = _make_ctx(query="What is MoE?")

        with pytest.raises(RuntimeError, match="LLM unavailable"):
            await stage.execute(ctx)

    @pytest.mark.asyncio
    async def test_accepts_all_valid_sub_questions(self):
        """Should accept all valid sub-questions from LLM without truncation."""
        from minerva.pipeline.stages import DecomposeStageImpl

        llm = AsyncMock()
        llm.generate.return_value = "\n".join(f"Sub-question {i}" for i in range(10))

        stage = DecomposeStageImpl(llm=llm)
        ctx = _make_ctx(query="test")

        result = await stage.execute(ctx)

        assert len(result.sub_questions) == 10
        assert result.sub_questions == [f"Sub-question {i}" for i in range(10)]

    @pytest.mark.asyncio
    async def test_filters_short_and_empty_lines(self):
        """Lines shorter than 6 characters after stripping should be ignored."""
        from minerva.pipeline.stages import DecomposeStageImpl

        llm = AsyncMock()
        llm.generate.return_value = (
            "- Valid question here?\n"
            "  \n"
            "- X\n"  # too short (after strip: "X", len=1)
            "- Another valid question.\n"
        )

        stage = DecomposeStageImpl(llm=llm)
        ctx = _make_ctx(query="test")

        result = await stage.execute(ctx)

        assert len(result.sub_questions) == 2
        assert "X" not in result.sub_questions


# ===================================================================
# MultiSourceSearchStageImpl
# ===================================================================


class TestMultiSourceSearchStageImpl:
    """Tests for MultiSourceSearchStageImpl — parallel multi-backend search."""

    @pytest.mark.asyncio
    async def test_searches_each_sub_question(self):
        """Should call search_engine.search() for each sub-question."""
        from minerva.pipeline.stages import MultiSourceSearchStageImpl

        r1 = MagicMock()
        r1.title = "R1"
        r1.url = "http://a.com"
        r1.snippet = "S1"
        r1.source = "web"
        r1.published_date = "2024-01-01"
        r1.rank_score = 0.9

        r2 = MagicMock()
        r2.title = "R2"
        r2.url = "http://b.com"
        r2.snippet = "S2"
        r2.source = "scholar"
        r2.published_date = "2024-02-01"
        r2.rank_score = 0.8

        search_engine = MagicMock()
        search_engine.search = AsyncMock(side_effect=[[r1], [r2]])

        stage = MultiSourceSearchStageImpl(search_engine, backends=["ddg", "scholar"], max_results=10)
        ctx = _make_ctx(sub_questions=["Q1", "Q2"])

        result = await stage.execute(ctx)

        assert search_engine.search.call_count == 2
        # First call (i=0) uses max_results=10, subsequent calls use 5
        assert search_engine.search.call_args_list[0][1]["max_results"] == 10
        assert search_engine.search.call_args_list[1][1]["max_results"] == 5
        assert len(result.search_results) == 2
        assert result.search_results[0]["title"] == "R1"
        assert result.search_results[1]["title"] == "R2"

    @pytest.mark.asyncio
    async def test_falls_back_to_query_when_no_sub_questions(self):
        """When ctx.sub_questions is empty, search with ctx.query."""
        from minerva.pipeline.stages import MultiSourceSearchStageImpl

        r = MagicMock()
        r.title = "Solo"
        r.url = "http://solo.com"
        r.snippet = "S"
        r.source = "web"
        r.published_date = "2024-01-01"
        r.rank_score = 0.5

        search_engine = MagicMock()
        search_engine.search = AsyncMock(return_value=[r])

        stage = MultiSourceSearchStageImpl(search_engine, backends=["ddg"], max_results=10)
        ctx = _make_ctx(query="fallback query", sub_questions=[])

        await stage.execute(ctx)

        search_engine.search.assert_called_once()
        assert search_engine.search.call_args[0][0] == "fallback query"

    @pytest.mark.asyncio
    async def test_deduplicates_by_url(self):
        """Results with the same URL should only appear once."""
        from minerva.pipeline.stages import MultiSourceSearchStageImpl

        r1 = MagicMock()
        r1.title = "Dup A"
        r1.url = "http://dup.com"
        r1.snippet = "S1"
        r1.source = "ddg"
        r1.published_date = "2024-01-01"
        r1.rank_score = 0.9

        r2 = MagicMock()
        r2.title = "Dup B"
        r2.url = "http://dup.com"
        r2.snippet = "S2"
        r2.source = "brave"
        r2.published_date = "2024-01-02"
        r2.rank_score = 0.8

        search_engine = MagicMock()
        search_engine.search = AsyncMock(side_effect=[[r1, r2]])

        stage = MultiSourceSearchStageImpl(search_engine, backends=["ddg", "brave"], max_results=10)
        ctx = _make_ctx(sub_questions=["Q1"])

        result = await stage.execute(ctx)

        assert len(result.search_results) == 1
        assert result.search_results[0]["title"] == "Dup A"

    @pytest.mark.asyncio
    async def test_handles_search_exceptions_gracefully(self):
        """Individual search failures should not block other results."""
        from minerva.pipeline.stages import MultiSourceSearchStageImpl

        r = MagicMock()
        r.title = "Good"
        r.url = "http://good.com"
        r.snippet = "OK"
        r.source = "web"
        r.published_date = "2024-01-01"
        r.rank_score = 0.5

        search_engine = MagicMock()
        search_engine.search = AsyncMock(
            side_effect=[
                RuntimeError("Backend failed"),
                [r],
            ]
        )

        stage = MultiSourceSearchStageImpl(search_engine, backends=["ddg"], max_results=10)
        ctx = _make_ctx(sub_questions=["Q1", "Q2"])

        result = await stage.execute(ctx)

        assert len(result.search_results) == 1
        assert result.search_results[0]["title"] == "Good"


# ===================================================================
# EntityExtractionStageImpl
# ===================================================================


class TestEntityExtractionStageImpl:
    """Tests for EntityExtractionStageImpl — spaCy NER + KB upsert."""

    @pytest.mark.asyncio
    async def test_extracts_entities_from_search_results(self):
        """Should run spaCy NER on search result content and populate ctx.entities."""
        from minerva.pipeline.stages import EntityExtractionStageImpl

        org_ent = _make_spacy_ent("ORG", "OpenAI")
        person_ent = _make_spacy_ent("PERSON", "Ilya Sutskever")
        mock_doc = _make_spacy_doc(org_ent, person_ent)
        mock_nlp = MagicMock(return_value=mock_doc)

        stage = EntityExtractionStageImpl(
            nlp=mock_nlp,
        )
        ctx = _make_ctx(
            search_results=[
                _make_search_result(content="OpenAI was founded by Ilya Sutskever."),
                _make_search_result(content="Another result."),
            ]
        )

        result = await stage.execute(ctx)

        assert len(result.entities) >= 2
        entity_types = {e.type for e in result.entities}
        assert "organization" in entity_types
        assert "person" in entity_types
        entity_names = {e.name for e in result.entities}
        assert "OpenAI" in entity_names
        assert "Ilya Sutskever" in entity_names

    @pytest.mark.asyncio
    async def test_skips_empty_content(self):
        """Results with no content should not cause NER processing."""
        from minerva.pipeline.stages import EntityExtractionStageImpl

        mock_doc = _make_spacy_doc()
        mock_nlp = MagicMock(return_value=mock_doc)

        stage = EntityExtractionStageImpl(
            nlp=mock_nlp,
        )
        ctx = _make_ctx(
            search_results=[
                _make_search_result(title="", snippet=""),
                _make_search_result(content="Valid content text here."),
            ]
        )

        await stage.execute(ctx)

        # Only one call — first result has no content, second has content
        assert mock_nlp.call_count == 1

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_nlp_pipeline(self):
        """When nlp_pipeline is None, entities should be empty."""
        from minerva.pipeline.stages import EntityExtractionStageImpl

        stage = EntityExtractionStageImpl(
            nlp=None,
        )
        ctx = _make_ctx(search_results=[_make_search_result()])

        result = await stage.execute(ctx)

        assert result.entities == []

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_content_text(self):
        """When content is empty across all results, entities should stay empty."""
        from minerva.pipeline.stages import EntityExtractionStageImpl

        mock_nlp = MagicMock()
        stage = EntityExtractionStageImpl(
            nlp=mock_nlp,
        )
        ctx = _make_ctx(
            search_results=[
                _make_search_result(title="", snippet=""),
            ]
        )

        result = await stage.execute(ctx)

        assert result.entities == []
        mock_nlp.assert_not_called()


# ===================================================================
# DeepReadStageImpl
# ===================================================================


class TestDeepReadStageImpl:
    """Tests for DeepReadStageImpl — content extraction + LLM analysis."""

    @pytest.mark.asyncio
    async def test_builds_document_text_and_sends_to_llm(self):
        """Should build doc text from search results and send to LLM for analysis."""
        from minerva.pipeline.stages import DeepReadStageImpl

        llm = AsyncMock()
        llm.generate.return_value = "Analysis: MoE is a neural network architecture."

        stage = DeepReadStageImpl(llm=llm)
        ctx = _make_ctx(
            query="What is MoE?",
            search_results=[
                _make_search_result(url="http://a.com", title="Doc A", snippet="Content about MoE."),
                _make_search_result(url="http://b.com", title="Doc B", snippet="More details on MoE."),
            ],
        )

        result = await stage.execute(ctx)

        assert llm.generate.call_count == 1
        prompt_text = llm.generate.call_args[0][0]
        assert "What is MoE?" in prompt_text
        assert "Content about MoE" in prompt_text
        assert "More details on MoE" in prompt_text
        assert result.deep_analysis == "Analysis: MoE is a neural network architecture."

    @pytest.mark.asyncio
    async def test_handles_empty_search_results(self):
        """When no search results, should return early without calling LLM."""
        from minerva.pipeline.stages import DeepReadStageImpl

        llm = AsyncMock()
        stage = DeepReadStageImpl(llm=llm)
        ctx = _make_ctx(search_results=[])

        result = await stage.execute(ctx)

        llm.generate.assert_not_called()
        # deep_analysis should not be set when no results are processed
        assert not hasattr(result, "deep_analysis") or not result.deep_analysis

    @pytest.mark.asyncio
    async def test_handles_llm_exception_propagates(self):
        """When LLM fails, exception should propagate."""
        from minerva.pipeline.stages import DeepReadStageImpl

        llm = AsyncMock()
        llm.generate.side_effect = RuntimeError("LLM down")

        stage = DeepReadStageImpl(llm=llm)
        ctx = _make_ctx(
            search_results=[
                _make_search_result(url="http://a.com", title="Doc A", snippet="Content."),
            ]
        )

        with pytest.raises(RuntimeError, match="LLM down"):
            await stage.execute(ctx)

    @pytest.mark.asyncio
    async def test_falls_back_to_snippet_when_content_missing(self):
        """Should use snippet when content field is not available."""
        from minerva.pipeline.stages import DeepReadStageImpl

        llm = AsyncMock()
        llm.generate.return_value = "Analysis."

        stage = DeepReadStageImpl(llm=llm)
        ctx = _make_ctx(
            query="test",
            search_results=[
                _make_search_result(snippet="Fallback snippet text."),
            ],
        )

        await stage.execute(ctx)

        prompt_text = llm.generate.call_args[0][0]
        assert "Fallback snippet text." in prompt_text


# ===================================================================
# CrossAnalyzeStageImpl
# ===================================================================


class TestCrossAnalyzeStageImpl:
    """Tests for CrossAnalyzeStageImpl — deep reasoning on contradictions."""

    @pytest.mark.asyncio
    async def test_analyzes_contradictions(self):
        """Should aggregate contradiction analyses and send for deep reasoning."""
        from minerva.pipeline.stages import CrossAnalyzeStageImpl

        llm = AsyncMock()
        llm.generate.return_value = "Deep reasoning result."

        stage = CrossAnalyzeStageImpl(llm)
        ctx = _make_ctx(
            query="What is AGI?",
            contradictions=[
                {"analysis": "Source A claims X."},
                {"analysis": "Source B refutes X."},
            ],
        )

        result = await stage.execute(ctx)

        assert llm.generate.call_count >= 1  # deep_read + optional verifier
        assert len(result.relations) == 1
        assert result.relations[0]["reasoning"] == "Deep reasoning result."

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_contradictions(self):
        """When no contradiction analysis exists, relations should stay empty."""
        from minerva.pipeline.stages import CrossAnalyzeStageImpl

        llm = AsyncMock()
        stage = CrossAnalyzeStageImpl(llm)
        ctx = _make_ctx(contradictions=[])

        result = await stage.execute(ctx)

        assert result.relations == []
        llm.generate.assert_not_called()

    @pytest.mark.asyncio
    async def test_handles_llm_exception_gracefully(self):
        """When LLM fails, a fallback message should be stored."""
        from minerva.pipeline.stages import CrossAnalyzeStageImpl

        llm = AsyncMock()
        llm.generate.side_effect = RuntimeError("LLM down")

        stage = CrossAnalyzeStageImpl(llm)
        ctx = _make_ctx(contradictions=[{"analysis": "Some analysis text."}])

        result = await stage.execute(ctx)

        assert len(result.relations) == 1
        assert result.relations[0]["reasoning"] == "Cross-analysis unavailable."


# ===================================================================
# QualityGateStageImpl
# ===================================================================


class TestQualityGateStageImpl:
    """Tests for QualityGateStageImpl — research quality scoring."""

    @pytest.mark.asyncio
    async def test_passes_with_good_quality(self):
        """Should assign score 100 when all quality checks pass."""
        from minerva.pipeline.stages import QualityGateStageImpl

        stage = QualityGateStageImpl()
        ctx = _make_ctx(
            search_results=[
                _make_search_result(source="scholar"),
                _make_search_result(source="web"),
                _make_search_result(source="ddg"),
                _make_search_result(source="brave"),
                _make_search_result(source="exa"),
            ],
            entities=[{"id": "e1", "type": "Person", "name": "X"}],
            contradictions=[{"analysis": "x" * 60}],
        )

        result = await stage.execute(ctx)

        assert len(result.relations) == 1
        assert result.relations[0]["quality_score"] == 100
        assert result.relations[0]["quality_gate_checks"]["source_count"] == 5
        assert result.relations[0]["quality_gate_checks"]["entity_count"] == 1
        assert result.relations[0]["failures"] == []

    @pytest.mark.asyncio
    async def test_fails_with_no_search_results(self):
        """Zero search results should trigger QualityGateError with score 0."""
        from minerva.pipeline.stages import QualityGateStageImpl

        stage = QualityGateStageImpl()
        ctx = _make_ctx(search_results=[])

        with pytest.raises(QualityGateError) as exc_info:
            await stage.execute(ctx)

        assert "No search results found" in str(exc_info.value)
        assert "No search results found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_fails_with_insufficient_sources_under_3(self):
        """Fewer than 3 sources should deduct 30 points and raise failure."""
        from minerva.pipeline.stages import QualityGateStageImpl

        stage = QualityGateStageImpl()
        ctx = _make_ctx(
            search_results=[
                _make_search_result(source="web"),
                _make_search_result(source="web"),
            ]
        )

        with pytest.raises(QualityGateError) as exc_info:
            await stage.execute(ctx)

        assert "Insufficient sources" in str(exc_info.value)
        assert "Insufficient sources" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_deducts_for_few_sources_under_5(self):
        """3-4 sources should deduct 10 points but not fail if other checks pass."""
        from minerva.pipeline.stages import QualityGateStageImpl

        stage = QualityGateStageImpl()
        ctx = _make_ctx(
            search_results=[
                _make_search_result(source="web"),
                _make_search_result(source="scholar"),
                _make_search_result(source="ddg"),
            ],
            entities=[{"id": "e1", "type": "Org"}],
            contradictions=[{"analysis": "x" * 60}],
        )

        result = await stage.execute(ctx)

        assert result.relations[0]["quality_score"] <= 90

    @pytest.mark.asyncio
    async def test_deducts_for_no_entities(self):
        """Missing entities should deduct 10 points."""
        from minerva.pipeline.stages import QualityGateStageImpl

        stage = QualityGateStageImpl()
        ctx = _make_ctx(
            search_results=[
                _make_search_result(source="scholar"),
                _make_search_result(source="web"),
                _make_search_result(source="ddg"),
            ],
            entities=[],  # no entities
            contradictions=[{"analysis": "x" * 60}],
        )

        result = await stage.execute(ctx)

        assert result.relations[0]["quality_score"] <= 90  # deduction for no entities

    @pytest.mark.asyncio
    async def test_deducts_for_single_source_backend(self):
        """All results from a single backend should deduct 15 points."""
        from minerva.pipeline.stages import QualityGateStageImpl

        stage = QualityGateStageImpl()
        ctx = _make_ctx(
            search_results=[
                _make_search_result(source="web"),
                _make_search_result(source="web"),
                _make_search_result(source="web"),
                _make_search_result(source="web"),
                _make_search_result(source="web"),
            ],
            entities=[{"id": "e1", "type": "Org"}],
            contradictions=[{"analysis": "x" * 60}],
        )

        result = await stage.execute(ctx)

        assert result.relations[0]["quality_score"] == 85  # 100 - 15 single source

    @pytest.mark.asyncio
    async def test_deducts_for_empty_contradiction_analysis(self):
        """Contradictions without substantive analysis should deduct 10 points."""
        from minerva.pipeline.stages import QualityGateStageImpl

        stage = QualityGateStageImpl()
        ctx = _make_ctx(
            search_results=[
                _make_search_result(source="scholar"),
                _make_search_result(source="web"),
                _make_search_result(source="ddg"),
            ],
            entities=[{"id": "e1", "type": "Org"}],
            contradictions=[{"analysis": ""}, {"analysis": "short"}],  # both < 50
        )

        result = await stage.execute(ctx)

        # 100 - 10 (for missing substantive analysis) = 90
        assert result.relations[0]["quality_score"] <= 90


# ===================================================================
# OutputStageImpl
# ===================================================================


class TestOutputStageImpl:
    """Tests for OutputStageImpl — report generation via execute()."""

    @pytest.mark.asyncio
    async def test_execute_populates_report(self, tmp_path):
        """Execute should populate ctx.report with formatted template and summary."""
        from minerva.pipeline.stages import OutputStageImpl

        llm = AsyncMock()
        llm.generate.return_value = "Summary of research findings."

        stage = OutputStageImpl(llm=llm, report_dir=str(tmp_path))
        ctx = _make_ctx(
            query="Test Query",
            search_results=[
                _make_search_result(title="R1", snippet="Content 1", source="web"),
                _make_search_result(title="R2", snippet="Content 2", source="scholar"),
            ],
            entities=[{"id": "e1", "type": "Person"}],
            relations=[{"quality_score": 85}],
        )

        result = await stage.execute(ctx)

        assert result.report is not None
        assert "Test Query" in result.report
        assert "Research Report" in result.report
        assert "Summary of research findings." in result.report
        assert "85" in result.report  # quality score
        assert "2" in result.report  # source count

    @pytest.mark.asyncio
    async def test_execute_handles_empty_search_results(self, tmp_path):
        """Should produce a report even with empty search results."""
        from minerva.pipeline.stages import OutputStageImpl

        llm = AsyncMock()
        llm.generate.return_value = "No findings."

        stage = OutputStageImpl(llm=llm, report_dir=str(tmp_path))
        ctx = _make_ctx(query="Empty", search_results=[])

        result = await stage.execute(ctx)

        assert result.report is not None
        assert "Empty" in result.report
        assert "No specific findings extracted." in result.report
        assert "No sources recorded." in result.report

    @pytest.mark.asyncio
    async def test_execute_calls_llm_with_context(self, tmp_path):
        """Should pass query and context to LLM for summary generation."""
        from minerva.pipeline.stages import OutputStageImpl

        llm = AsyncMock()
        llm.generate.return_value = "Summary."

        stage = OutputStageImpl(llm=llm, report_dir=str(tmp_path))
        ctx = _make_ctx(
            query="Test Query",
            search_results=[
                _make_search_result(title="R1", snippet="Content 1"),
            ],
            entities=[{"id": "e1", "type": "Person"}],
        )

        await stage.execute(ctx)

        assert llm.generate.call_count == 1
        prompt = llm.generate.call_args[0][0]
        assert "Test Query" in prompt
        assert "1" in prompt  # source count
        assert "1" in prompt  # entity count


# ===================================================================
# CounterArgumentStageImpl
# ===================================================================


class TestCounterArgumentStageImpl:
    """Tests for CounterArgumentStageImpl — devil's advocate analysis (L3+)."""

    @pytest.mark.asyncio
    async def test_generates_counter_arguments_from_contradictions(self):
        """Should send contradiction analysis to LLM and store counter argument."""
        from minerva.pipeline.stages import CounterArgumentStageImpl

        llm = AsyncMock()
        llm.generate.return_value = "Counter-argument: the methodology is flawed."

        stage = CounterArgumentStageImpl(llm)
        ctx = _make_ctx(
            query="Is AGI near?",
            contradictions=[
                {"analysis": "Some claim AGI is near."},
            ],
        )

        result = await stage.execute(ctx)

        assert llm.generate.call_count >= 1  # deep_read + optional verifier
        assert len(result.relations) == 1
        assert result.relations[0]["counter_argument"] == "Counter-argument: the methodology is flawed."

    @pytest.mark.asyncio
    async def test_falls_back_to_search_results_when_no_contradictions(self):
        """When no contradiction analysis, should use search results as findings."""
        from minerva.pipeline.stages import CounterArgumentStageImpl

        llm = AsyncMock()
        llm.generate.return_value = "Counter-arguments based on search."

        stage = CounterArgumentStageImpl(llm)
        ctx = _make_ctx(
            query="Test",
            contradictions=[],
            search_results=[
                _make_search_result(title="R1", snippet="Snippet one."),
                _make_search_result(title="R2", snippet="Snippet two."),
            ],
        )

        await stage.execute(ctx)

        assert llm.generate.call_count >= 1  # deep_read + optional verifier
        prompt_text = llm.generate.call_args[1]["prompt"]
        assert "R1" in prompt_text
        assert "Snippet one" in prompt_text

    @pytest.mark.asyncio
    async def test_handles_llm_exception_gracefully(self):
        """Should store fallback message when LLM fails."""
        from minerva.pipeline.stages import CounterArgumentStageImpl

        llm = AsyncMock()
        llm.generate.side_effect = RuntimeError("LLM down")

        stage = CounterArgumentStageImpl(llm)
        ctx = _make_ctx(
            query="Test",
            contradictions=[{"analysis": "Some analysis."}],
        )

        result = await stage.execute(ctx)

        assert result.relations[0]["counter_argument"] == "Counter-argument analysis unavailable."


# ===================================================================
# MultiModelVotingStageImpl
# ===================================================================


class TestMultiModelVotingStageImpl:
    """Tests for MultiModelVotingStageImpl — multi-model voting (L4)."""

    @pytest.mark.asyncio
    async def test_votes_on_conclusions(self):
        """Should aggregate relations and send to LLM for multi-model voting."""
        from minerva.pipeline.stages import MultiModelVotingStageImpl

        llm = AsyncMock()
        llm.generate.return_value = "Voting: AGREE on claim 1, DISAGREE on claim 2."

        stage = MultiModelVotingStageImpl(llm)
        ctx = _make_ctx(
            query="What is the future of AI?",
            relations=[
                {"reasoning": "Deep reasoning result."},
                {"counter_argument": "Alternative perspective."},
            ],
        )

        result = await stage.execute(ctx)

        assert llm.generate.call_count >= 1  # deep_read + optional verifier
        assert len(result.relations) == 3  # 2 original + 1 voting
        assert result.relations[-1]["voting"] == "Voting: AGREE on claim 1, DISAGREE on claim 2."

    @pytest.mark.asyncio
    async def test_returns_insufficient_data_when_no_relations(self):
        """Should store fallback message when no relation data is available."""
        from minerva.pipeline.stages import MultiModelVotingStageImpl

        llm = AsyncMock()
        stage = MultiModelVotingStageImpl(llm)
        ctx = _make_ctx(query="Test", relations=[])

        result = await stage.execute(ctx)

        llm.generate.assert_not_called()
        assert len(result.relations) == 1
        assert "Insufficient data" in result.relations[0]["voting"]

    @pytest.mark.asyncio
    async def test_handles_llm_exception_gracefully(self):
        """Should store fallback message when LLM fails."""
        from minerva.pipeline.stages import MultiModelVotingStageImpl

        llm = AsyncMock()
        llm.generate.side_effect = RuntimeError("LLM down")

        stage = MultiModelVotingStageImpl(llm)
        ctx = _make_ctx(
            query="Test",
            relations=[{"reasoning": "Some reasoning."}],
        )

        result = await stage.execute(ctx)

        assert result.relations[-1]["voting"] == "Multi-model voting unavailable."


# ===================================================================
# ExtendedOutputStageImpl (L4)
# ===================================================================


class TestExtendedOutputStageImpl:
    """Tests for ExtendedOutputStageImpl — L4 extended report."""

    @pytest.mark.asyncio
    async def test_generates_report_via_parent(self, tmp_path):
        """Should delegate to parent execute and produce a report."""
        from minerva.pipeline.stages import ExtendedOutputStageImpl

        llm = AsyncMock()
        llm.generate.return_value = "Extended summary text."

        stage = ExtendedOutputStageImpl(llm=llm, report_dir=str(tmp_path))
        ctx = _make_ctx(
            query="Extended Research",
            level=ResearchLevel.L4,
            search_results=[
                _make_search_result(title="Key Paper", source="scholar"),
                _make_search_result(title="Supporting Study", source="web"),
            ],
            entities=[{"id": "e1", "type": "Tech"}],
            cost=2.50,
        )

        result = await stage.execute(ctx)

        assert result.report is not None
        assert "Extended Research" in result.report
        assert "Extended summary text." in result.report

    @pytest.mark.asyncio
    async def test_handles_empty_search_results(self, tmp_path):
        """Should gracefully handle empty search results."""
        from minerva.pipeline.stages import ExtendedOutputStageImpl

        llm = AsyncMock()
        llm.generate.return_value = "Summary."

        stage = ExtendedOutputStageImpl(llm=llm, report_dir=str(tmp_path))
        ctx = _make_ctx(
            query="Basic L4",
            level=ResearchLevel.L4,
            search_results=[],
            cost=0.0,
        )

        result = await stage.execute(ctx)

        assert result.report is not None
        assert "Basic L4" in result.report
        assert "No specific findings extracted." in result.report
        assert "No sources recorded." in result.report


# ===================================================================
# spacy_to_entity_type (module-level helper)
# ===================================================================


class TestSpacyToEntityType:
    """Tests for the spacy_to_entity_type mapping function."""

    def test_known_labels(self):
        """Should map known spaCy NER labels to Minerva ontology types."""
        from minerva.shared import spacy_to_entity_type

        assert spacy_to_entity_type("ORG") == "Organization"
        assert spacy_to_entity_type("PERSON") == "Person"
        assert spacy_to_entity_type("GPE") == "Organization"
        assert spacy_to_entity_type("PRODUCT") == "Product"
        assert spacy_to_entity_type("WORK_OF_ART") == "Publication"
        assert spacy_to_entity_type("DATE") == "Event"
        assert spacy_to_entity_type("EVENT") == "Event"

    def test_unknown_label_defaults_to_concept(self):
        """Unknown labels should map to 'Concept'."""
        from minerva.shared import spacy_to_entity_type

        assert spacy_to_entity_type("MONEY") == "Concept"
        assert spacy_to_entity_type("UNKNOWN_LABEL") == "Concept"
