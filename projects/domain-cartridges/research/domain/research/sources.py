"""Paper source adapters with circuit-breaker style network guards.

Each adapter implements `fetch(query, limit)` and returns a list of `Paper`
dataclasses.  Network failures are caught and logged, never raised — this is the
circuit_breaker: "论文抓取网络异常时安全跳过并记录日志" (BET-Y2Q4-T7-01).

`AbstractPaperSource` is a deterministic in-memory source used by tests and as a
fallback so the pipeline remains exercisable offline.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Protocol

logger = logging.getLogger(__name__)


@dataclass
class Paper:
    """One fetched paper, normalized across sources."""

    id: str
    title: str
    abstract: str
    source: str
    url: str = ""
    keywords: list[str] = field(default_factory=list)
    published: str = ""


class PaperSource(Protocol):
    name: str

    def fetch(self, query: str, limit: int = 10) -> list[Paper]: ...


class AbstractPaperSource:
    """Deterministic offline source for tests and local exercise."""

    name = "abstract"

    def __init__(self, papers: list[Paper] | None = None) -> None:
        self._papers = papers or []

    def fetch(self, query: str, limit: int = 10) -> list[Paper]:
        q = query.lower()
        hits = [p for p in self._papers if q in p.title.lower() or q in p.abstract.lower()]
        return hits[:limit]


class _HttpSourceMixin:
    """Shared network guard: any transport failure degrades to empty, never raises."""

    timeout: float = 5.0

    def _safe_get(self, url: str) -> str:
        """Fetch a URL; return "" on any network error (circuit_breaker)."""
        try:
            import urllib.request

            req = urllib.request.Request(url, headers={"User-Agent": "omo-research-cartridge/0.1"})
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except Exception as exc:  # noqa: BLE001 - deliberate circuit breaker
            logger.warning("[%s] fetch failed for %s: %s (skipping)", self.name, url, exc)
            return ""


class PubmedSource(_HttpSourceMixin, AbstractPaperSource):
    """PubMed E-utilities (esearch + esummary). Empty on network failure."""

    name = "pubmed"

    def fetch(self, query: str, limit: int = 10) -> list[Paper]:
        base = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
        xml = self._safe_get(
            f"{base}/esearch.fcgi?db=pubmed&term={query}&retmax={limit}&retmode=json"
        )
        if not xml:
            return []
        try:
            import json

            ids = json.loads(xml).get("esearchresult", {}).get("idlist", [])[:limit]
        except Exception:  # noqa: BLE001
            return []
        papers: list[Paper] = []
        for pmid in ids:
            summary = self._safe_get(f"{base}/esummary.fcgi?db=pubmed&id={pmid}&retmode=json")
            if not summary:
                continue
            try:
                res = json.loads(summary)["result"][pmid]
            except Exception:  # noqa: BLE001
                continue
            papers.append(
                Paper(
                    id=pmid,
                    title=res.get("title", ""),
                    abstract=res.get("abstract", ""),
                    source=self.name,
                    url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                    keywords=[k for k in (res.get("keywords") or []) if k][:8],
                )
            )
        return papers


class BiorxivSource(_HttpSourceMixin, AbstractPaperSource):
    """BioRxiv API (limited to recent listings). Empty on network failure."""

    name = "biorxiv"

    def fetch(self, query: str, limit: int = 10) -> list[Paper]:
        url = f"https://api.biorxiv.org/details/biorxiv/2020-01-01/0/{limit}"
        raw = self._safe_get(url)
        if not raw:
            return []
        try:
            import json

            items = json.loads(raw).get("collection") or []
        except Exception:  # noqa: BLE001
            return []
        papers: list[Paper] = []
        for it in items:
            title = it.get("title", "")
            abstract = it.get("abstract", "")
            if query.lower() not in title.lower() and query.lower() not in abstract.lower():
                continue
            papers.append(
                Paper(
                    id=str(it.get("doi", "")),
                    title=title,
                    abstract=abstract,
                    source=self.name,
                    url=it.get("url", ""),
                    keywords=[],
                    published=it.get("date", ""),
                )
            )
        return papers[:limit]


class ArxivSource(_HttpSourceMixin, AbstractPaperSource):
    """arXiv API (Atom feed). Empty on network failure."""

    name = "arxiv"

    def fetch(self, query: str, limit: int = 10) -> list[Paper]:
        url = (
            f"http://export.arxiv.org/api/query?search_query=all:{query}"
            f"&start=0&max_results={limit}"
        )
        atom = self._safe_get(url)
        if not atom:
            return []
        try:
            import xml.etree.ElementTree as ET

            ns = {"a": "http://www.w3.org/2005/Atom"}
            root = ET.fromstring(atom)
            papers = []
            for entry in root.findall("a:entry", ns):
                title = (entry.findtext("a:title", default="", namespaces=ns) or "").strip()
                summary = (entry.findtext("a:summary", default="", namespaces=ns) or "").strip()
                papers.append(
                    Paper(
                        id=(entry.findtext("a:id", default="", namespaces=ns) or "").strip(),
                        title=title,
                        abstract=summary,
                        source=self.name,
                        url=(entry.findtext("a:id", default="", namespaces=ns) or "").strip(),
                        keywords=[],
                        published=(entry.findtext("a:published", default="", namespaces=ns) or "").strip(),
                    )
                )
            return papers[:limit]
        except Exception:  # noqa: BLE001
            return []


def default_sources() -> list[PaperSource]:
    """Ordered source list used by the pipeline."""
    return [PubmedSource(), BiorxivSource(), ArxivSource()]
