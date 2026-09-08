"""Self-test for the research deep-synthesis pipeline (verify entry).

Run: `uv run python -m domain.research.test_synthesis_pipeline` from
`projects/domain-cartridges/research/` (exit 0 = pass).

Covers: source normalization, relevance filtering, Top-3 selection, three-part
synthesis cards, technology matrix, and offline pipeline end-to-end execution.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure the cartridge package is importable when invoked as a module from the
# cartridge directory (uv run python -m domain.research.test_synthesis_pipeline).
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from .filter import filter_relevant, select_top_n
from .pipeline import ResearchPipeline
from .sources import AbstractPaperSource, Paper
from .synthesis import TechOption, synthesize_card, technology_matrix

FAILURES: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    if cond:
        print(f"PASS  {name}")
    else:
        print(f"FAIL  {name} {detail}")
        FAILURES.append(name)


def _sample_papers() -> list[Paper]:
    return [
        Paper(
            id="p1",
            title="Large language models for biomedical literature",
            abstract="We survey LLM applications in biomedical NLP, including summarization.",
            source="abstract",
            keywords=["llm", "biomedical"],
        ),
        Paper(
            id="p2",
            title="Retrieval augmented generation in scientific discovery",
            abstract="RAG pipelines improve answer quality over scientific corpora.",
            source="abstract",
            keywords=["rag"],
        ),
        Paper(
            id="p3",
            title="Unrelated study of soil chemistry",
            abstract="No machine learning content in this abstract at all.",
            source="abstract",
            keywords=["soil"],
        ),
    ]


def test_filter_and_select() -> None:
    papers = _sample_papers()
    scored = filter_relevant(papers, ["large language model", "scientific discovery"], min_score=1.0)
    selected = select_top_n(scored, n=2)
    ids = [p.id for p in selected]
    check("filter keeps relevant", len(scored) == 2, f"got {len(scored)}")
    check("irrelevant excluded", "p3" not in ids, f"ids={ids}")
    check("top-n respects score order", ids[0] == "p1", f"ids={ids}")


def test_synthesis_card() -> None:
    paper = _sample_papers()[0]
    card = synthesize_card(paper, topics=["large language model"])
    check("card has abstract part", len(card.abstract_part) > 0)
    check("card has method part", "Source" in card.method_part)
    check("card has impact part", "frontier" in card.impact_part)
    check("card confidence > 0", card.confidence > 0.0)


def test_technology_matrix() -> None:
    options = [
        TechOption(name="A", scores={"cost": 4.0, "accuracy": 3.0}, notes=""),
        TechOption(name="B", scores={"cost": 2.0, "accuracy": 5.0}, notes=""),
        TechOption(name="C", scores={"cost": 5.0, "accuracy": 1.0}, notes=""),
    ]
    rows = technology_matrix(options, ["cost", "accuracy"])
    totals = [r["total"] for r in rows]
    check("matrix rows sorted by total desc", totals == sorted(totals, reverse=True), f"totals={totals}")
    check("matrix carries dimension scores", rows[0]["cost"] >= 0 and rows[0]["accuracy"] >= 0)


def test_pipeline_offline() -> None:
    source = AbstractPaperSource(_sample_papers())
    pipeline = ResearchPipeline(sources=[source], top_n=3)
    cards = pipeline.run(["large language model"], min_score=1.0)
    check("offline pipeline returns cards", len(cards) >= 1, f"got {len(cards)}")
    check("offline cards are three-part", all(c.abstract_part and c.method_part and c.impact_part for c in cards))


def main() -> int:
    print("=== domain.research.test_synthesis_pipeline ===")
    test_filter_and_select()
    test_synthesis_card()
    test_technology_matrix()
    test_pipeline_offline()
    if FAILURES:
        print(f"\n{len(FAILURES)} FAILURES: {FAILURES}")
        return 1
    print("\nAll research-cartridge checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
