"""End-to-end research deep-synthesis pipeline.

Flow: fetch from all sources (network-safe) -> relevance filter -> daily Top-3
selection -> three-part synthesis cards -> optional technology matrix.

The pipeline is fully exercisable offline via `AbstractPaperSource`; real HTTP
sources degrade to empty on network failure (circuit_breaker), never raise.
"""

from __future__ import annotations

import argparse
import json
import logging
from typing import Iterable

from .filter import filter_relevant, select_top_n
from .sources import PaperSource, default_sources
from .synthesis import DeepSynthesisCard, TechOption, synthesize_card, technology_matrix

logger = logging.getLogger(__name__)


class ResearchPipeline:
    """Compose sources + filter + synthesis into one runnable stage."""

    def __init__(
        self,
        sources: Iterable[PaperSource] | None = None,
        *,
        top_n: int = 3,
    ) -> None:
        self.sources = list(sources) if sources is not None else default_sources()
        self.top_n = top_n

    def run(
        self,
        topics: list[str],
        *,
        limit: int = 10,
        min_score: float = 1.0,
    ) -> list[DeepSynthesisCard]:
        """Fetch, filter, select and synthesize; returns synthesis cards."""
        collected: list[tuple] = []
        for source in self.sources:
            papers = source.fetch(" ".join(topics), limit=limit)
            scored = filter_relevant(papers, topics, min_score=min_score)
            collected.extend(scored)
        selected = select_top_n(collected, n=self.top_n)
        cards = [synthesize_card(paper, topics=topics) for paper in selected]
        return cards


def _cli() -> int:
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description="Research deep-synthesis pipeline")
    parser.add_argument("--topics", nargs="+", default=["large language model"])
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--offline",
        action="store_true",
        help="use deterministic abstract source instead of network",
    )
    args = parser.parse_args()

    pipeline = ResearchPipeline()
    cards = pipeline.run(args.topics, limit=args.limit)
    payload = [card.to_dict() for card in cards]
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        for card in cards:
            print(f"- {card.paper.source}: {card.paper.title}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
