"""Best-First Tree Search (BFTS) — deep iterative branching research."""

from __future__ import annotations

import asyncio
from typing import Any

import structlog

from minerva.search.bfs_search_types import (
    BFTSNode,
    collect_completed,
    count_nodes,
    create_child,
    create_root,
)

logger = structlog.get_logger(__name__)


# Default source trust scores (0.0–1.0) — immutable source-of-truth
# Instances get their own copy via __init__ to prevent cross-instance mutation.
_SOURCE_TRUST_DEFAULTS: dict[str, float] = {
    "arxiv": 1.0,
    "scholar": 0.9,
    "searxng": 0.8,
    "exa": 0.8,
    "metaso": 0.7,
    "brave": 0.6,
    "zhipu": 0.5,
    "ddg": 0.5,
}

DEFAULT_TRUST: float = 0.5


class BFTSearch:
    """Best-First Tree Search engine.

    Iteratively explores research questions by:
    1. Decomposing into sub-questions (parallel fan-out)
    2. Searching each sub-question
    3. Scoring and pruning branches
    4. Continuing best branches deeper
    5. Synthesizing results into a cohesive output
    """

    def __init__(
        self,
        search_engine: Any,
        llm_client: Any = None,
        max_depth: int = 3,
        max_branches: int = 5,
        prune_threshold: float = 0.3,
    ) -> None:
        self.search_engine = search_engine
        self.llm_client = llm_client
        self.max_depth = max_depth
        self.max_branches = max_branches
        self.prune_threshold = prune_threshold
        # Instance-level copy of source trust to prevent cross-instance mutation
        self.source_trust: dict[str, float] = dict(_SOURCE_TRUST_DEFAULTS)

    # ============================================================
    # Public API
    # ============================================================

    async def search(self, query: str) -> dict:
        """Run Best-First Tree Search.

        Args:
            query: The research question.

        Returns:
            dict with keys: query, max_depth, branches_explored, depth_reached,
            pruned_count, synthesis
        """
        root = create_root(query)
        branches_explored = 0
        pruned_count = 0

        # Explore root level
        root_results = await self._explore(root)
        root.results = root_results
        root.score = self._score_branch(root)
        root.status = "completed"
        branches_explored += 1

        # BFS expansion: explore level by level
        current_level: list[BFTSNode] = [root]

        for depth in range(1, self.max_depth + 1):
            # Decompose each node at current level
            children: list[BFTSNode] = []
            for node in current_level:
                sub_queries = await self._decompose(node.query)
                for sq in sub_queries:
                    child = create_child(node, sq)
                    children.append(child)

            if not children:
                break

            # Explore all children in parallel
            explore_tasks = [self._explore_and_score(child) for child in children]
            await asyncio.gather(*explore_tasks, return_exceptions=True)
            branches_explored += len(children)

            # Prune
            previous_count = len(children)
            kept = self._prune(children)
            pruned_count += previous_count - len(kept)

            # Mark kept children as completed
            for node in kept:
                node.status = "completed"

            current_level = kept
            if not current_level:
                break

        # Synthesize
        completed = collect_completed(root)
        synthesis = self._synthesize(completed)
        node_counts = count_nodes(root)

        return {
            "query": query,
            "max_depth": self.max_depth,
            "branches_explored": branches_explored,
            "depth_reached": min(self.max_depth, node_counts["total"] - 1),
            "pruned_count": pruned_count,
            "synthesis": synthesis,
        }

    # ============================================================
    # Decompose: question → sub-questions
    # ============================================================

    async def _decompose(self, query: str) -> list[str]:
        """Decompose a research question into sub-questions.

        Uses LLM if available, otherwise returns the original query as a single
        sub-question. Empty query returns empty list.
        """
        if not query:
            return []

        if self.llm_client is None:
            return [query]

        prompt = (
            "You are a research assistant. Decompose the following research question "
            "into focused, specific sub-questions. Each sub-question should be "
            "self-contained and answerable through web search.\n\n"
            f"Question: {query}\n\n"
            "Return each sub-question on a new line, numbered (1., 2., etc.)."
        )

        try:
            result = await self.llm_client.generate(
                system="You decompose research questions into searchable sub-questions. Respond only with the numbered list.",
                prompt=prompt,
                temperature=0.3,
                max_tokens=512,
            )
            sub_questions = self._parse_numbered_list(result)
            if not sub_questions:
                return [query]
            return sub_questions[: self.max_branches]
        except Exception:
            logger.warning("decompose_failed", query=query)
            return [query]

    @staticmethod
    def _parse_numbered_list(text: str) -> list[str]:
        """Parse a numbered list from LLM output.

        Accepts formats: "1. Item", "1 Item", "1.Item"
        """
        items: list[str] = []
        for line in text.strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            # Remove numbering: "1. text", "1 text", "1.text"
            for sep in (". ", ".", " "):
                parts = line.split(sep, 1)
                if len(parts) == 2 and parts[0].strip().isdigit():
                    items.append(parts[1].strip())
                    break
        return items

    # ============================================================
    # Explore: search for a node's question
    # ============================================================

    async def _explore(self, node: BFTSNode) -> list[dict]:
        """Execute search for a node's query.

        Sets node.status = "exploring" and returns search result dicts.
        """
        node.status = "exploring"
        try:
            search_results = await self.search_engine.search(node.query)
            results = [
                {
                    "title": r.title,
                    "url": r.url,
                    "snippet": r.snippet,
                    "source": getattr(r, "source", "unknown"),
                    "published_date": getattr(r, "published_date", None),
                    "rank_score": getattr(r, "rank_score", 0.0),
                }
                for r in search_results
            ]
            return results
        except Exception:
            logger.warning("explore_failed", query=node.query)
            return []

    async def _explore_and_score(self, node: BFTSNode) -> None:
        """Explore a node, store results, and score it."""
        results = await self._explore(node)
        node.results = results
        node.score = self._score_branch(node)
        if self._should_prune(node):
            node.status = "pruned"

    def _should_prune(self, node: BFTSNode) -> bool:
        """Check if a node should be pruned based on its score."""
        return node.score < self.prune_threshold

    # ============================================================
    # Score: evaluate branch quality
    # ============================================================

    def _score_branch(self, node: BFTSNode) -> float:
        """Score a branch based on result relevance and source trust.

        score = avg_rank_score * avg_source_trust
        Returns 0.0 if no results.
        """
        if not node.results:
            return 0.0

        total_rank = 0.0
        total_trust = 0.0
        count = 0

        for r in node.results:
            rank = r.get("rank_score", 0.0)
            source = r.get("source", "unknown")
            trust = self.source_trust.get(source, DEFAULT_TRUST)
            total_rank += rank
            total_trust += trust
            count += 1

        if count == 0:
            return 0.0

        avg_rank = total_rank / count
        avg_trust = total_trust / count
        return avg_rank * avg_trust

    # ============================================================
    # Prune: filter low-quality branches
    # ============================================================

    def _prune(self, nodes: list[BFTSNode]) -> list[BFTSNode]:
        """Prune low-scoring branches.

        Keeps branches with score >= prune_threshold, sorted by score descending.
        Caps at max_branches. If all below threshold, keeps top-1 as fallback.
        Marks pruned nodes with status="pruned".

        Returns:
            List of kept nodes.
        """
        if not nodes:
            return []

        # Sort by score descending
        sorted_nodes = sorted(nodes, key=lambda n: n.score, reverse=True)

        # Find those above threshold
        kept: list[BFTSNode] = []

        for node in sorted_nodes:
            if node.score >= self.prune_threshold and len(kept) < self.max_branches:
                kept.append(node)
            else:
                node.status = "pruned"

        # Fallback: keep at least top-1
        if not kept and sorted_nodes:
            kept.append(sorted_nodes[0])
            sorted_nodes[0].status = "pending"

        return kept

    # ============================================================
    # Synthesize: merge results into final output
    # ============================================================

    @staticmethod
    def _synthesize(nodes: list[BFTSNode]) -> dict:
        """Merge results from multiple completed branches.

        Deduplicates by URL, sorts by rank_score descending.
        """
        seen_urls: set = set()
        all_results: list[dict] = []

        for node in nodes:
            for r in node.results:
                url = r.get("url", "")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    all_results.append(r)

        # Sort by rank_score descending
        all_results.sort(key=lambda r: r.get("rank_score", 0.0), reverse=True)

        # Branch info
        branches = [{"query": n.query, "depth": n.depth, "score": n.score} for n in nodes]

        return {
            "total_branches": len(nodes),
            "total_results": len(all_results),
            "results": all_results,
            "branches": branches,
        }
