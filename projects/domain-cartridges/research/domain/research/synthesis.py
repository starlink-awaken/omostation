"""Deep-synthesis card generation and technology-selection trade-off matrix.

A synthesis card has three parts (摘要/方法/影响):
- abstract: one-paragraph plain-language summary
- method:   what the paper actually does (approach, claims, evidence)
- impact:   what changes if the result holds (for our knowledge system / stack)

The technology matrix scores candidate options against decision dimensions so a
major system-selection question can be weighed explicitly.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .sources import Paper


@dataclass
class DeepSynthesisCard:
    """Three-part reading card for one paper."""

    paper: Paper
    abstract_part: str
    method_part: str
    impact_part: str
    confidence: float = 0.5

    def to_dict(self) -> dict:
        return {
            "paper_id": self.paper.id,
            "title": self.paper.title,
            "source": self.paper.source,
            "url": self.paper.url,
            "abstract": self.abstract_part,
            "method": self.method_part,
            "impact": self.impact_part,
            "confidence": self.confidence,
        }


def _first_sentences(text: str, n: int = 2) -> str:
    import re

    parts = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
    return " ".join(parts[:n]) if parts else text[:200]


def synthesize_card(paper: Paper, *, topics: list[str] | None = None) -> DeepSynthesisCard:
    """Build a three-part card from a normalized Paper (deterministic)."""
    topics = topics or []
    topic_hits = [t for t in topics if t.lower() in f"{paper.title} {paper.abstract}".lower()]
    abstract_part = _first_sentences(paper.abstract) or "(abstract not available)"
    method_part = (
        f"Source {paper.source}; title: {paper.title}. "
        f"Relevant topic keywords matched: {topic_hits if topic_hits else 'none'}."
    )
    impact_part = (
        "Tracked as frontier literature candidate for knowledge-graph / stack "
        "selection updates. Detailed method extraction requires full-text access."
    )
    confidence = min(1.0, 0.3 + 0.1 * len(topic_hits))
    return DeepSynthesisCard(
        paper=paper,
        abstract_part=abstract_part,
        method_part=method_part,
        impact_part=impact_part,
        confidence=confidence,
    )


@dataclass
class TechOption:
    """One candidate technology in the selection matrix."""

    name: str
    scores: dict[str, float] = field(default_factory=dict)  # dimension -> 0..5
    notes: str = ""


def technology_matrix(
    options: list[TechOption],
    dimensions: list[str],
) -> list[dict]:
    """Score options against dimensions; return a sortable matrix with totals."""
    rows = []
    for opt in options:
        total = sum(opt.scores.get(d, 0.0) for d in dimensions)
        rows.append(
            {
                "option": opt.name,
                **{d: opt.scores.get(d, 0.0) for d in dimensions},
                "total": total,
                "notes": opt.notes,
            }
        )
    rows.sort(key=lambda r: r["total"], reverse=True)
    return rows
