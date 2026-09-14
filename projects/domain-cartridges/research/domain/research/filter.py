"""Relevance filtering and daily Top-N selection.

Filtering is deliberately lightweight: keyword-overlap scoring with no external
NLP dependency so the cartridge runs in any uv environment.  The Top-3 daily
selection prefers the highest-scoring papers across all sources.
"""

from __future__ import annotations

from collections import Counter

from .sources import Paper

STOPWORDS = {
    "a", "an", "the", "of", "and", "or", "for", "in", "on", "with", "to",
    "from", "by", "is", "are", "was", "were", "be", "been", "at", "as",
}


def _tokens(text: str) -> set[str]:
    words = [w.strip(".,;:()[]{}'\"") for w in text.lower().split()]
    return {w for w in words if w and w not in STOPWORDS and len(w) > 2}


def filter_relevant(
    papers: list[Paper],
    topics: list[str],
    *,
    min_score: float = 1.0,
) -> list[tuple[Paper, float]]:
    """Score papers against topic keywords; keep those above min_score.

    Returns (paper, score) pairs, score = count of distinct topic tokens found
    in the paper's title+abstract.
    """
    topic_tokens = Counter()
    for topic in topics:
        topic_tokens.update(_tokens(topic))
    if not topic_tokens:
        return [(p, 0.0) for p in papers]
    scored: list[tuple[Paper, float]] = []
    for paper in papers:
        text = f"{paper.title} {paper.abstract}"
        hits = sum(count for tok, count in topic_tokens.items() if tok in text)
        score = float(hits)
        if score >= min_score:
            scored.append((paper, score))
    return scored


def select_top_n(
    scored: list[tuple[Paper, float]],
    n: int = 3,
) -> list[Paper]:
    """Select the top-N papers by score, stable on ties (source order kept)."""
    ranked = sorted(scored, key=lambda pair: pair[1], reverse=True)
    return [paper for paper, _ in ranked[:n]]
