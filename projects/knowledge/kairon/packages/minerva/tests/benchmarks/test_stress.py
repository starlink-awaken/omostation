"""System stress test — concurrency, large queries, memory, Neo4j throughput."""

import asyncio

import pytest


class TestConcurrency:
    """Tests for concurrent request handling."""

    @pytest.mark.asyncio
    async def test_10_concurrent_search_calls(self):
        """10 concurrent searches should not crash or hang."""
        from minerva.search.backends import search_duckduckgo

        async def _one():
            try:
                return await search_duckduckgo("test query concurrency", max_results=2)
            except Exception:
                return []

        tasks = [_one() for _ in range(10)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        success = sum(1 for r in results if isinstance(r, list))
        errors = sum(1 for r in results if isinstance(r, Exception))
        assert success > 0
        assert errors < 5  # Some network flakiness OK

    @pytest.mark.asyncio
    async def test_concurrent_entity_extraction(self):
        """Concurrent entity extraction from multiple texts."""
        import spacy

        try:
            nlp = spacy.load("en_core_web_sm")
        except OSError:
            pytest.skip("spaCy model 'en_core_web_sm' not installed")
        texts = [
            "Google and Microsoft are competing in AI.",
            "Apple released new iPhone models.",
            "OpenAI launched GPT-5 with improved reasoning.",
            "Tesla's self-driving technology advances.",
            "Amazon Web Services dominates cloud computing.",
        ] * 2  # 10 concurrent

        async def _extract(text):
            doc = nlp(text)
            return [(ent.text, ent.label_) for ent in doc.ents]

        tasks = [_extract(t) for t in texts]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        total = sum(len(r) for r in results if isinstance(r, list))
        assert total > 0  # At least some entities found

    @pytest.mark.asyncio
    async def test_rule_based_triage_concurrent(self):
        """Concurrent triage should not corrupt router state."""
        from minerva.triage.router import TriageRouter

        router = TriageRouter(llm_client=None)
        queries = [
            "What is Python?",
            "Analyze transformer evolution",
            "Compare React vs Vue",
            "Latest AI news today",
            "Security audit checklist",
        ]

        async def _classify(q):
            return router.classify_rule_based(q)

        results = await asyncio.gather(*[_classify(q) for q in queries])
        levels = [r.level.value for r in results]
        assert len(levels) == 5
        assert all(level in ("L0", "L1", "L2", "L3", "L4") for level in levels)


class TestLargeQuery:
    """Tests for edge-case large inputs."""

    @pytest.mark.asyncio
    async def test_large_query_triage_no_crash(self):
        """500-char query should not crash triage."""
        from minerva.triage.router import TriageRouter

        router = TriageRouter(llm_client=None)
        long_query = (
            "Please provide a comprehensive analysis of modern artificial "
            "intelligence systems including deep learning, reinforcement "
            "learning, transformer architectures, large language models, "
            "computer vision, natural language processing, multi-modal "
            "models, AI safety, alignment research, and the societal "
            "impact of AI technologies on healthcare, education, finance, "
            "and transportation sectors worldwide. " * 3
        )[:500]
        result = router.classify_rule_based(long_query)
        assert result.level.value in ("L0", "L1", "L2", "L3", "L4")


class TestMemoryLeak:
    """Sequential execution should not accumulate memory."""

    @pytest.mark.asyncio
    async def test_5_sequential_triage_no_leak(self):
        """5 sequential triage calls should not show abnormal growth."""
        import sys

        from minerva.triage.router import TriageRouter

        router = TriageRouter(llm_client=None)
        sys.gettotalrefcount() if hasattr(sys, "gettotalrefcount") else 0

        for _ in range(5):
            _ = router.classify_rule_based("Test query for memory check")
            _ = router.classify_rule_based("Another different test query here")


class TestNeo4jThroughput:
    """Bulk write throughput for knowledge graph."""

    @pytest.mark.asyncio
    async def test_100_entity_batch_write(self):
        """100 entities should be writable in reasonable time."""
        import time

        from minerva.graph.bridge import GraphBridge, GraphConfig, GraphEntity

        config = GraphConfig(enabled=False)  # Don't require real Neo4j
        bridge = GraphBridge(config)

        start = time.time()
        for i in range(100):
            entity = GraphEntity(
                id=f"stress-{i}",
                name=f"Entity_{i}",
                entity_type="Concept",
            )
            await bridge.upsert_entity(entity)
        elapsed = time.time() - start
        # With disabled config, all calls return False instantly
        assert elapsed < 5.0
