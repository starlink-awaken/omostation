# ---
# domain: workflows
# layer: tool
# status: active
# ---
"""Orchestrate external perception pipeline. STEPS entry point.

Migrated from SharedBrain-code/workflows/perception/run_perception.py to KOS kairon.
"""

from __future__ import annotations

import json
import logging

_log = logging.getLogger(__name__)


def run_perceive(goal: str, auto: bool = True) -> bool:
    from kos.perception.fact_injector import inject_facts  # type: ignore[import-not-found]
    from kos.perception.scrape import scrape_url  # type: ignore[import-not-found]
    from kos.perception.search import web_search  # type: ignore[import-not-found]

    print("  >> [external search]")
    results = web_search(goal)
    print(f"    {len(results)} search results")

    if not results:
        print("    No search results -- skipped scraping and injection")
        return False

    print("  >> [web scrape]")
    scraped = []
    for r in results[:3]:
        url = r.get("url", "")
        if url:
            content = scrape_url(url)
            if content:
                scraped.append(content)
    print(f"    {len(scraped)} pages scraped")

    print("  >> [fact injection]")
    facts = []
    for s in scraped:
        facts.append(
            {
                "sub": s.get("title", goal)[:100],
                "pred": "external_reference",
                "obj": s.get("url", ""),
                "metadata": json.dumps({"source": "web_scrape", "snippet": s.get("text_content", "")[:200]}),
            }
        )
    count = inject_facts(facts)
    print(f"    {count} facts injected into FactGraph")
    return count > 0
