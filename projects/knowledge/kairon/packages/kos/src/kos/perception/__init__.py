"""Perception module — web search, scraping, and fact injection."""

from kos.perception.fact_injector import inject_facts as inject_facts  # type: ignore[import-not-found]
from kos.perception.scrape import scrape_url as scrape_url  # type: ignore[import-not-found]
from kos.perception.search import web_search as web_search  # type: ignore[import-not-found]
