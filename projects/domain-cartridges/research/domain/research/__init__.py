"""Research deep-synthesis cartridge.

Automated tracking of frontier literature (PubMed / BioRxiv / arXiv) with:
- source adapters that degrade gracefully on network failure (circuit_breaker)
- relevance filtering and daily Top-3 selection
- three-part deep-synthesis cards (abstract / method / impact)
- technology-selection trade-off matrix output

Entry: `uv run python -m domain.research.test_synthesis_pipeline` (self-test),
or `uv run python -m domain.research.pipeline --topics "..."`
"""

from .filter import filter_relevant, select_top_n
from .pipeline import ResearchPipeline
from .sources import AbstractPaperSource, ArxivSource, BiorxivSource, PubmedSource
from .synthesis import DeepSynthesisCard, synthesize_card, technology_matrix

__all__ = [
    "ResearchPipeline",
    "PubmedSource",
    "BiorxivSource",
    "ArxivSource",
    "AbstractPaperSource",
    "filter_relevant",
    "select_top_n",
    "DeepSynthesisCard",
    "synthesize_card",
    "technology_matrix",
]
