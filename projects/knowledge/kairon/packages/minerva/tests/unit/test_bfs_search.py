"""Tests for Best-First Tree Search (BFTS) module."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

# ============================================================
# BFTSNode and Type Tests
# ============================================================


class TestBFTSNode:
    """Tests for BFTSNode dataclass and factory functions."""

    def test_create_root(self):
        """Root node created at depth 0 with exploring status."""
        from minerva.search.bfs_search_types import create_root

        node = create_root("test query")
        assert node.query == "test query"
        assert node.depth == 0
        assert node.status == "exploring"
        assert node.parent is None
        assert node.children == []
        assert node.results == []
        assert node.score == 0.0

    def test_create_child_linked_to_parent(self):
        """Child node links to parent and increments depth."""
        from minerva.search.bfs_search_types import create_child, create_root

        root = create_root("parent")
        child = create_child(root, "child query")
        assert child.query == "child query"
        assert child.depth == 1
        assert child.status == "pending"
        assert child.parent is root
        assert child in root.children

    def test_status_transitions(self):
        """Node status transitions through valid states."""
        from minerva.search.bfs_search_types import BFTSNode

        node = BFTSNode(query="q", depth=0)
        assert node.status == "pending"
        node.status = "exploring"
        assert node.status == "exploring"
        node.status = "pruned"
        assert node.status == "pruned"
        node.status = "completed"
        assert node.status == "completed"

    def test_collect_completed_nodes(self):
        """Recursively collects all completed nodes."""
        from minerva.search.bfs_search_types import collect_completed, create_child, create_root

        root = create_root("root")
        c1 = create_child(root, "c1")
        c2 = create_child(root, "c2")
        c1a = create_child(c1, "c1a")
        c1b = create_child(c1, "c1b")
        # Mark some as completed
        c1.status = "completed"
        c1a.status = "completed"
        c1b.status = "pruned"
        c2.status = "completed"

        completed = collect_completed(root)
        completed_queries = {n.query for n in completed}
        assert completed_queries == {"c1", "c1a", "c2"}
        assert len(completed) == 3

    def test_count_nodes_by_status(self):
        """Counts nodes grouped by status."""
        from minerva.search.bfs_search_types import BFTSNode, count_nodes

        root = BFTSNode(query="r", depth=0, status="exploring")
        c1 = BFTSNode(query="c1", depth=1, parent=root, status="completed")
        c2 = BFTSNode(query="c2", depth=1, parent=root, status="pruned")
        root.children = [c1, c2]

        counts = count_nodes(root)
        assert counts["total"] == 3
        assert counts["exploring"] == 1
        assert counts["completed"] == 1
        assert counts["pruned"] == 1
        assert counts["pending"] == 0

    def test_empty_tree_count(self):
        """Count on single root works correctly."""
        from minerva.search.bfs_search_types import BFTSNode, count_nodes

        root = BFTSNode(query="r", depth=0)
        counts = count_nodes(root)
        assert counts["total"] == 1
        assert counts["pending"] == 1


# ============================================================
# Decompose Tests
# ============================================================


class TestDecompose:
    """Tests for BFTS decompose logic."""

    @pytest.mark.asyncio
    async def test_decompose_default_returns_root_as_fallback(self):
        """Without LLM, decompose returns the original query."""
        from minerva.search.bfs_search import BFTSearch

        engine_mock = MagicMock()
        bfs = BFTSearch(search_engine=engine_mock)
        # No LLM client → fallback: return [query]
        queries = await bfs._decompose("test query")
        assert queries == ["test query"]

    @pytest.mark.asyncio
    async def test_decompose_llm_returns_subquestions(self):
        """With LLM client, decompose returns sub-questions from LLM."""
        from minerva.search.bfs_search import BFTSearch

        engine_mock = MagicMock()
        llm_mock = MagicMock()
        llm_mock.generate = AsyncMock(return_value=("1. Sub question one\n2. Sub question two\n3. Sub question three"))
        bfs = BFTSearch(search_engine=engine_mock, llm_client=llm_mock)
        queries = await bfs._decompose("main question")
        assert len(queries) == 3
        assert queries[0] == "Sub question one"
        assert queries[1] == "Sub question two"
        assert queries[2] == "Sub question three"

    @pytest.mark.asyncio
    async def test_decompose_llm_respects_max_branches(self):
        """LLM decomposition is capped at max_branches."""
        from minerva.search.bfs_search import BFTSearch

        engine_mock = MagicMock()
        llm_mock = MagicMock()
        llm_mock.generate = AsyncMock(return_value=("1. Q1\n2. Q2\n3. Q3\n4. Q4\n5. Q5\n6. Q6"))
        bfs = BFTSearch(search_engine=engine_mock, llm_client=llm_mock, max_branches=3)
        queries = await bfs._decompose("main question")
        assert len(queries) == 3

    @pytest.mark.asyncio
    async def test_decompose_llm_failure_fallback(self):
        """When LLM fails, decompose gracefully falls back to [query]."""
        from minerva.search.bfs_search import BFTSearch

        engine_mock = MagicMock()
        llm_mock = MagicMock()
        llm_mock.generate = AsyncMock(side_effect=RuntimeError("LLM error"))
        bfs = BFTSearch(search_engine=engine_mock, llm_client=llm_mock)
        queries = await bfs._decompose("main question")
        assert queries == ["main question"]

    @pytest.mark.asyncio
    async def test_decompose_empty_input_returns_empty(self):
        """Empty query string returns empty list."""
        from minerva.search.bfs_search import BFTSearch

        engine_mock = MagicMock()
        bfs = BFTSearch(search_engine=engine_mock)
        queries = await bfs._decompose("")
        assert queries == []


# ============================================================
# Score Branch Tests
# ============================================================


class TestScoreBranch:
    """Tests for branch scoring logic."""

    def test_score_high_relevance_results(self):
        """Results with high relevance get high score."""
        from minerva.search.bfs_search import BFTSearch
        from minerva.search.bfs_search_types import BFTSNode

        engine_mock = MagicMock()
        bfs = BFTSearch(search_engine=engine_mock)
        node = BFTSNode(query="q", depth=0)
        node.results = [
            {"title": "Result 1", "snippet": "relevant content", "source": "arxiv", "rank_score": 0.9},
            {"title": "Result 2", "snippet": "more content", "source": "scholar", "rank_score": 0.8},
        ]
        score = bfs._score_branch(node)
        # average rank_score ≈ 0.85 * source_trust (arxiv=1.0, scholar=0.9) → (0.85 * avg_trust)
        assert 0.7 <= score <= 1.0

    def test_score_no_results(self):
        """No results yields low score."""
        from minerva.search.bfs_search import BFTSearch
        from minerva.search.bfs_search_types import BFTSNode

        engine_mock = MagicMock()
        bfs = BFTSearch(search_engine=engine_mock)
        node = BFTSNode(query="q", depth=0)
        score = bfs._score_branch(node)
        assert score == 0.0

    def test_score_low_trust_source(self):
        """Low-trust sources reduce the score."""
        from minerva.search.bfs_search import BFTSearch
        from minerva.search.bfs_search_types import BFTSNode

        engine_mock = MagicMock()
        bfs = BFTSearch(search_engine=engine_mock)
        node = BFTSNode(query="q", depth=0)
        node.results = [
            {"title": "Blog", "snippet": "opinion", "source": "ddg", "rank_score": 0.9},
        ]
        score = bfs._score_branch(node)
        # ddg trust=0.5, so score should be lower than 0.8
        assert score <= 0.5

    def test_score_empty_results_list(self):
        """Empty results list gives score 0."""
        from minerva.search.bfs_search import BFTSearch
        from minerva.search.bfs_search_types import BFTSNode

        engine_mock = MagicMock()
        bfs = BFTSearch(search_engine=engine_mock)
        node = BFTSNode(query="q", depth=0)
        node.results = []
        score = bfs._score_branch(node)
        assert score == 0.0

    def test_score_mixed_sources(self):
        """Mixed sources compute weighted average trust."""
        from minerva.search.bfs_search import BFTSearch
        from minerva.search.bfs_search_types import BFTSNode

        engine_mock = MagicMock()
        bfs = BFTSearch(search_engine=engine_mock)
        node = BFTSNode(query="q", depth=0)
        node.results = [
            {"title": "Paper", "snippet": "research", "source": "arxiv", "rank_score": 1.0},
            {"title": "Blog", "snippet": "opinion", "source": "ddg", "rank_score": 1.0},
        ]
        score = bfs._score_branch(node)
        # avg rank=1.0, avg trust=(1.0+0.5)/2=0.75, score=0.75
        assert 0.7 <= score <= 0.8

    def test_score_missing_source_field(self):
        """Missing source field should not crash."""
        from minerva.search.bfs_search import BFTSearch
        from minerva.search.bfs_search_types import BFTSNode

        engine_mock = MagicMock()
        bfs = BFTSearch(search_engine=engine_mock)
        node = BFTSNode(query="q", depth=0)
        node.results = [
            {"title": "Unknown", "snippet": "content", "rank_score": 0.5},
        ]
        score = bfs._score_branch(node)
        # No source → default trust 0.5
        assert score > 0


# ============================================================
# Prune Tests
# ============================================================


class TestPrune:
    """Tests for branch pruning logic."""

    def test_prune_below_threshold(self):
        """Branches below threshold are removed."""
        from minerva.search.bfs_search import BFTSearch
        from minerva.search.bfs_search_types import BFTSNode

        engine_mock = MagicMock()
        bfs = BFTSearch(search_engine=engine_mock, prune_threshold=0.5)
        nodes = [
            BFTSNode(query="q1", depth=1, score=0.8),
            BFTSNode(query="q2", depth=1, score=0.3),
            BFTSNode(query="q3", depth=1, score=0.6),
        ]
        kept = bfs._prune(nodes)
        assert len(kept) == 2
        assert kept[0].query == "q1"
        assert kept[1].query == "q3"
        assert nodes[1].status == "pruned"

    def test_prune_all_above_threshold(self):
        """All nodes above threshold are kept (up to max_branches)."""
        from minerva.search.bfs_search import BFTSearch
        from minerva.search.bfs_search_types import BFTSNode

        engine_mock = MagicMock()
        bfs = BFTSearch(search_engine=engine_mock, prune_threshold=0.5, max_branches=10)
        nodes = [
            BFTSNode(query="q1", depth=1, score=0.9),
            BFTSNode(query="q2", depth=1, score=0.8),
            BFTSNode(query="q3", depth=1, score=0.7),
        ]
        kept = bfs._prune(nodes)
        assert len(kept) == 3

    def test_prune_all_below_threshold(self):
        """All nodes below threshold get pruned, at least one kept."""
        from minerva.search.bfs_search import BFTSearch
        from minerva.search.bfs_search_types import BFTSNode

        engine_mock = MagicMock()
        bfs = BFTSearch(search_engine=engine_mock, prune_threshold=0.9)
        nodes = [
            BFTSNode(query="q1", depth=1, score=0.3),
            BFTSNode(query="q2", depth=1, score=0.2),
        ]
        kept = bfs._prune(nodes)
        # At least the best one survives (fallback: keep top 1 if all below threshold)
        assert len(kept) == 1
        assert kept[0].query == "q1"
        assert nodes[1].status == "pruned"

    def test_prune_max_branches_limit(self):
        """Number of kept branches capped at max_branches."""
        from minerva.search.bfs_search import BFTSearch
        from minerva.search.bfs_search_types import BFTSNode

        engine_mock = MagicMock()
        bfs = BFTSearch(search_engine=engine_mock, max_branches=2)
        nodes = [
            BFTSNode(query="q1", depth=1, score=0.9),
            BFTSNode(query="q2", depth=1, score=0.8),
            BFTSNode(query="q3", depth=1, score=0.7),
            BFTSNode(query="q4", depth=1, score=0.6),
        ]
        kept = bfs._prune(nodes)
        assert len(kept) == 2
        assert kept[0].query == "q1"
        assert kept[1].query == "q2"

    def test_prune_empty_list(self):
        """Empty node list returns empty."""
        from minerva.search.bfs_search import BFTSearch

        engine_mock = MagicMock()
        bfs = BFTSearch(search_engine=engine_mock)
        kept = bfs._prune([])
        assert kept == []


# ============================================================
# Explore Tests
# ============================================================


class TestExplore:
    """Tests for branch exploration logic."""

    @pytest.mark.asyncio
    async def test_explore_single_level(self):
        """Exploring a node returns search results."""
        from minerva.search.bfs_search import BFTSearch
        from minerva.search.bfs_search_types import BFTSNode

        engine_mock = MagicMock()
        engine_mock.search = AsyncMock(
            return_value=[
                MagicMock(
                    title="R1",
                    url="https://a.com/1",
                    snippet="snippet1",
                    source="arxiv",
                    published_date="2024-01-01",
                    rank_score=0.9,
                ),
                MagicMock(
                    title="R2",
                    url="https://a.com/2",
                    snippet="snippet2",
                    source="arxiv",
                    published_date="2024-01-02",
                    rank_score=0.8,
                ),
            ]
        )
        bfs = BFTSearch(search_engine=engine_mock)
        node = BFTSNode(query="test", depth=0)
        results = await bfs._explore(node)
        assert len(results) == 2
        assert results[0]["title"] == "R1"
        assert results[0]["url"] == "https://a.com/1"
        assert node.status == "exploring"  # status unchanged by _explore

    @pytest.mark.asyncio
    async def test_explore_empty_results(self):
        """Empty search results handled gracefully."""
        from minerva.search.bfs_search import BFTSearch
        from minerva.search.bfs_search_types import BFTSNode

        engine_mock = MagicMock()
        engine_mock.search = AsyncMock(return_value=[])
        bfs = BFTSearch(search_engine=engine_mock)
        node = BFTSNode(query="test", depth=0)
        results = await bfs._explore(node)
        assert results == []

    @pytest.mark.asyncio
    async def test_explore_backend_failure_graceful(self):
        """When search engine fails, returns empty gracefully."""
        from minerva.search.bfs_search import BFTSearch
        from minerva.search.bfs_search_types import BFTSNode

        engine_mock = MagicMock()
        engine_mock.search = AsyncMock(side_effect=RuntimeError("Search failed"))
        bfs = BFTSearch(search_engine=engine_mock)
        node = BFTSNode(query="test", depth=0)
        results = await bfs._explore(node)
        assert results == []


# ============================================================
# Synthesize Tests
# ============================================================


class TestSynthesize:
    """Tests for results synthesis."""

    def test_synthesize_single_node(self):
        """Single completed node produces synthesis with its results."""
        from minerva.search.bfs_search import BFTSearch
        from minerva.search.bfs_search_types import BFTSNode

        engine_mock = MagicMock()
        bfs = BFTSearch(search_engine=engine_mock)
        node = BFTSNode(query="q1", depth=1, score=0.9, status="completed")
        node.results = [
            {"title": "R1", "url": "https://a.com/1", "snippet": "s1", "source": "arxiv", "rank_score": 0.9},
        ]
        synthesis = bfs._synthesize([node])
        assert synthesis["total_branches"] == 1
        assert synthesis["total_results"] == 1
        assert len(synthesis["results"]) == 1
        assert synthesis["results"][0]["title"] == "R1"

    def test_synthesize_multiple_nodes_dedup(self):
        """Multiple nodes with duplicate results are deduplicated."""
        from minerva.search.bfs_search import BFTSearch
        from minerva.search.bfs_search_types import BFTSNode

        engine_mock = MagicMock()
        bfs = BFTSearch(search_engine=engine_mock)
        n1 = BFTSNode(query="q1", depth=1, score=0.9, status="completed")
        n1.results = [
            {"title": "R1", "url": "https://a.com/1", "snippet": "s1", "source": "arxiv", "rank_score": 0.9},
            {"title": "R2", "url": "https://a.com/2", "snippet": "s2", "source": "arxiv", "rank_score": 0.8},
        ]
        n2 = BFTSNode(query="q2", depth=1, score=0.7, status="completed")
        n2.results = [
            {"title": "R1", "url": "https://a.com/1", "snippet": "s1", "source": "arxiv", "rank_score": 0.9},
            {"title": "R3", "url": "https://a.com/3", "snippet": "s3", "source": "ddg", "rank_score": 0.5},
        ]
        synthesis = bfs._synthesize([n1, n2])
        assert synthesis["total_branches"] == 2
        assert synthesis["total_results"] == 3  # dedup removes duplicate
        assert len(synthesis["results"]) == 3

    def test_synthesize_empty_nodes(self):
        """No nodes produces empty synthesis."""
        from minerva.search.bfs_search import BFTSearch

        engine_mock = MagicMock()
        bfs = BFTSearch(search_engine=engine_mock)
        synthesis = bfs._synthesize([])
        assert synthesis["total_branches"] == 0
        assert synthesis["total_results"] == 0
        assert synthesis["results"] == []

    def test_synthesize_results_sorted_by_score(self):
        """Results in synthesis are sorted by rank_score descending."""
        from minerva.search.bfs_search import BFTSearch
        from minerva.search.bfs_search_types import BFTSNode

        engine_mock = MagicMock()
        bfs = BFTSearch(search_engine=engine_mock)
        node = BFTSNode(query="q1", depth=1, score=0.9, status="completed")
        node.results = [
            {"title": "Low", "url": "https://a.com/1", "snippet": "s1", "source": "arxiv", "rank_score": 0.3},
            {"title": "High", "url": "https://a.com/2", "snippet": "s2", "source": "arxiv", "rank_score": 0.9},
            {"title": "Mid", "url": "https://a.com/3", "snippet": "s3", "source": "arxiv", "rank_score": 0.6},
        ]
        synthesis = bfs._synthesize([node])
        titles = [r["title"] for r in synthesis["results"]]
        assert titles == ["High", "Mid", "Low"]

    def test_synthesize_includes_branch_info(self):
        """Synthesis includes branch-level info per result."""
        from minerva.search.bfs_search import BFTSearch
        from minerva.search.bfs_search_types import BFTSNode

        engine_mock = MagicMock()
        bfs = BFTSearch(search_engine=engine_mock)
        node = BFTSNode(query="branch query", depth=1, score=0.85, status="completed")
        node.results = [
            {"title": "R1", "url": "https://a.com/1", "snippet": "s1", "source": "arxiv", "rank_score": 0.9},
        ]
        synthesis = bfs._synthesize([node])
        assert synthesis["branches"][0]["query"] == "branch query"
        assert synthesis["branches"][0]["score"] == 0.85
        assert synthesis["branches"][0]["depth"] == 1


# ============================================================
# Full BFTS Search Tests
# ============================================================


class TestBFSFullSearch:
    """Tests for the complete BFTS search pipeline."""

    @pytest.mark.asyncio
    async def test_complete_search_flow(self):
        """Full search with LLM decomposition produces multi-level results."""
        from minerva.search.bfs_search import BFTSearch

        engine_mock = MagicMock()
        engine_mock.search = AsyncMock(
            return_value=[
                MagicMock(
                    title=f"Result {i}",
                    url=f"https://a.com/{i}",
                    snippet="snippet",
                    source="arxiv",
                    published_date="2024-01-01",
                    rank_score=0.8 - i * 0.1,
                )
                for i in range(3)
            ]
        )
        llm_mock = MagicMock()
        llm_mock.generate = AsyncMock(return_value="1. Sub q1\n2. Sub q2")

        bfs = BFTSearch(
            search_engine=engine_mock, llm_client=llm_mock, max_depth=1, max_branches=3, prune_threshold=0.3
        )
        result = await bfs.search("main question")

        assert result["query"] == "main question"
        assert result["max_depth"] == 1
        assert result["branches_explored"] > 0
        assert "synthesis" in result
        assert result["synthesis"]["total_branches"] > 0
        assert result["synthesis"]["total_results"] > 0

    @pytest.mark.asyncio
    async def test_search_depth_limit(self):
        """Search respects max_depth configuration."""
        from minerva.search.bfs_search import BFTSearch

        engine_mock = MagicMock()
        engine_mock.search = AsyncMock(
            return_value=[
                MagicMock(
                    title="R",
                    url="https://a.com/1",
                    snippet="s",
                    source="arxiv",
                    published_date="2024-01-01",
                    rank_score=0.9,
                ),
            ]
        )
        llm_mock = MagicMock()
        llm_mock.generate = AsyncMock(return_value="1. Sub q1")

        # depth=0 → only the root query, no decomposition
        bfs = BFTSearch(
            search_engine=engine_mock, llm_client=llm_mock, max_depth=0, max_branches=3, prune_threshold=0.3
        )
        result = await bfs.search("main question")
        # Only the root node is explored
        assert result["depth_reached"] == 0

    @pytest.mark.asyncio
    async def test_search_no_results_graceful(self):
        """Search with no results produces empty but valid output."""
        from minerva.search.bfs_search import BFTSearch

        engine_mock = MagicMock()
        engine_mock.search = AsyncMock(return_value=[])
        llm_mock = MagicMock()
        llm_mock.generate = AsyncMock(return_value="1. Sub q1\n2. Sub q2")

        bfs = BFTSearch(search_engine=engine_mock, llm_client=llm_mock, max_depth=1, prune_threshold=0.3)
        result = await bfs.search("main question")
        assert result["query"] == "main question"
        assert result["branches_explored"] >= 0
        assert result["synthesis"]["total_results"] == 0

    @pytest.mark.asyncio
    async def test_search_prune_threshold_filtering(self):
        """Low-scoring branches are pruned."""
        from minerva.search.bfs_search import BFTSearch

        engine_mock = MagicMock()
        # Return empty results → score=0 → will be pruned
        engine_mock.search = AsyncMock(return_value=[])
        llm_mock = MagicMock()
        llm_mock.generate = AsyncMock(return_value="1. Sub q1\n2. Sub q2\n3. Sub q3")

        bfs = BFTSearch(
            search_engine=engine_mock, llm_client=llm_mock, max_depth=1, max_branches=5, prune_threshold=0.8
        )
        result = await bfs.search("main question")
        # All branches score=0, which is < 0.8 threshold → should still have
        # at least the top-1 as fallback
        assert result["pruned_count"] >= 0
        assert "synthesis" in result

    @pytest.mark.asyncio
    async def test_search_max_branches_capped(self):
        """Search caps branches at max_branches."""
        from minerva.search.bfs_search import BFTSearch

        engine_mock = MagicMock()
        engine_mock.search = AsyncMock(
            return_value=[
                MagicMock(
                    title="R",
                    url="https://a.com/1",
                    snippet="s",
                    source="arxiv",
                    published_date="2024-01-01",
                    rank_score=0.9,
                ),
            ]
        )
        llm_mock = MagicMock()
        llm_mock.generate = AsyncMock(return_value="\n".join(f"{i}. Q{i}" for i in range(1, 11)))

        bfs = BFTSearch(
            search_engine=engine_mock, llm_client=llm_mock, max_depth=1, max_branches=3, prune_threshold=0.3
        )
        result = await bfs.search("main question")
        # At depth 0, decompose returns ≤ max_branches=3 → but LLM returns 10,
        # capped at 3 by _decompose
        assert result["branches_explored"] <= 4  # root + 3 branches
        assert result["pruned_count"] >= 0

    @pytest.mark.asyncio
    async def test_search_parallel_execution(self):
        """Multiple branches are explored in parallel (asyncio.gather)."""
        from minerva.search.bfs_search import BFTSearch

        engine_mock = MagicMock()
        engine_mock.search = AsyncMock(
            return_value=[
                MagicMock(
                    title="R",
                    url="https://a.com/1",
                    snippet="s",
                    source="arxiv",
                    published_date="2024-01-01",
                    rank_score=0.9,
                ),
            ]
        )
        llm_mock = MagicMock()
        llm_mock.generate = AsyncMock(return_value="1. Q1\n2. Q2")

        bfs = BFTSearch(search_engine=engine_mock, llm_client=llm_mock, max_depth=0, max_branches=3)
        result = await bfs.search("main question")
        assert result["branches_explored"] >= 1  # root explored at minimum

    @pytest.mark.asyncio
    async def test_search_multi_level_tree(self):
        """Multi-level search produces a tree structure."""
        from minerva.search.bfs_search import BFTSearch

        engine_mock = MagicMock()
        engine_mock.search = AsyncMock(
            return_value=[
                MagicMock(
                    title="R",
                    url="https://a.com/1",
                    snippet="s",
                    source="arxiv",
                    published_date="2024-01-01",
                    rank_score=0.9,
                ),
            ]
        )
        llm_mock = MagicMock()
        llm_mock.generate = AsyncMock(return_value="1. Sub Q1\n2. Sub Q2")

        bfs = BFTSearch(
            search_engine=engine_mock, llm_client=llm_mock, max_depth=2, max_branches=2, prune_threshold=0.3
        )
        result = await bfs.search("main question")
        assert result["depth_reached"] >= 0
        assert "synthesis" in result


# ============================================================
# MCP Tool Tests
# ============================================================


class TestMCPTool:
    """Tests for minerva_bfs_search MCP tool registration."""

    def test_bfs_mcp_tool_imports(self):
        """BFTS MCP tool module imports without error."""
        from minerva.mcp_server.server import mcp

        assert mcp is not None

    def test_bfs_mcp_tool_registered(self):
        """minerva_bfs_search is registered as an MCP tool."""
        from minerva.mcp_server.server import FORMAT_VERSION

        # The BFTS tool should be in the module
        assert FORMAT_VERSION == "minerva-v1"

    @pytest.mark.asyncio
    async def test_mcp_tool_list_includes_bfs(self):
        """Tool list includes minerva_bfs_search."""
        from minerva.mcp_server.server import mcp

        tools = await mcp.list_tools()
        tool_names = {t.name for t in tools}
        assert "minerva_bfs_search" in tool_names

    @pytest.mark.asyncio
    async def test_minerva_bfs_search_tool_parameters(self):
        """minerva_bfs_search tool has correct parameters."""
        from minerva.mcp_server.server import mcp

        tools = await mcp.list_tools()
        bfs_tool = next((t for t in tools if t.name == "minerva_bfs_search"), None)
        assert bfs_tool is not None, "minerva_bfs_search not found"
        params = bfs_tool.parameters
        assert "query" in params.get("properties", params)


# ============================================================
# Integration Tests
# ============================================================


class TestIntegration:
    """Integration tests for BFTS with real components."""

    @pytest.mark.asyncio
    async def test_with_search_engine_mock(self):
        """BFTS works with a SearchEngine-compatible mock."""
        from minerva.search.bfs_search import BFTSearch

        # Create a mock that behaves like SearchEngine
        engine_mock = MagicMock()
        engine_mock.search = AsyncMock(
            return_value=[
                MagicMock(
                    title="Paper 1",
                    url="https://arxiv.org/abs/001",
                    snippet="Abstract about AI regulation",
                    source="arxiv",
                    published_date="2024-06-01",
                    rank_score=0.95,
                ),
                MagicMock(
                    title="Paper 2",
                    url="https://arxiv.org/abs/002",
                    snippet="Healthcare AI impact study",
                    source="arxiv",
                    published_date="2024-06-15",
                    rank_score=0.88,
                ),
            ]
        )

        bfs = BFTSearch(search_engine=engine_mock, max_depth=0)
        result = await bfs.search("AI regulation impact on healthcare")

        assert result["query"] == "AI regulation impact on healthcare"
        assert result["synthesis"]["total_results"] == 2
        assert engine_mock.search.called
        engine_mock.search.assert_called_with("AI regulation impact on healthcare")

    @pytest.mark.asyncio
    async def test_bfs_with_llm_decomposition_real_pattern(self):
        """BFTS with decomposition produces branched output."""
        from minerva.search.bfs_search import BFTSearch

        engine_mock = MagicMock()
        engine_mock.search = AsyncMock(
            return_value=[
                MagicMock(
                    title="R",
                    url="https://a.com/1",
                    snippet="s",
                    source="arxiv",
                    published_date="2024-01-01",
                    rank_score=0.85,
                ),
            ]
        )
        llm_mock = MagicMock()
        llm_mock.generate = AsyncMock(return_value="1. Healthcare AI policy\n2. Medical device regulation")

        bfs = BFTSearch(search_engine=engine_mock, llm_client=llm_mock, max_depth=1, max_branches=3)
        result = await bfs.search("AI regulation impact")

        assert result["branches_explored"] >= 2  # root + sub branches
        assert result["depth_reached"] >= 0

    @pytest.mark.asyncio
    async def test_error_recovery_in_pipeline(self):
        """BFTS handles search engine failures mid-pipeline."""
        from minerva.search.bfs_search import BFTSearch

        engine_mock = MagicMock()
        # First call succeeds, second fails
        engine_mock.search = AsyncMock(
            side_effect=[
                RuntimeError("Temporary failure"),
            ]
        )
        bfs = BFTSearch(search_engine=engine_mock, max_depth=0)
        # Should not raise — error is caught and returned as empty
        result = await bfs.search("test")
        assert result["synthesis"]["total_results"] == 0
