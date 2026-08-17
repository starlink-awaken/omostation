"""Knowledge ingest pipeline — URL/PDF/Markdown → Entity + Relation extraction."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class IngestResult:
    """Result of an ingest operation."""

    source: str
    source_type: str
    entities_extracted: int = 0
    relations_found: int = 0
    content_saved: bool = False
    errors: list[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return len(self.errors) == 0


class KnowledgeIngester:
    """Ingest external content into the Minerva knowledge base.

    Supports:
    - URL (fetch + extract + parse)
    - Markdown files (parse + extract)
    - PDF files (text extraction only)

    Pipeline: Source → Extract text → spaCy NER → Entity + Relation → KnowledgeStore
    """

    def __init__(
        self, knowledge_store: Any = None, nlp_pipeline: Any = None, report_dir: str = "~/knowledge/ingested"
    ) -> None:
        self.kb = knowledge_store
        self.nlp = nlp_pipeline
        self.report_dir = Path(report_dir).expanduser()
        self.report_dir.mkdir(parents=True, exist_ok=True)

    async def ingest(self, source: str, source_type: str = "auto") -> IngestResult:
        """Ingest content from a source.

        Args:
            source: URL or local file path
            source_type: "url", "markdown", "pdf", or "auto" (detect from source)
        """
        if source_type == "auto":
            source_type = self._detect_type(source)

        result = IngestResult(source=source, source_type=source_type)

        # Step 1: Extract text content
        try:
            text = await self._extract_text(source, source_type)
        except Exception as e:
            result.errors.append(f"Extraction failed: {e}")
            return result

        if not text or len(text) < 10:
            result.errors.append("No meaningful text extracted")
            return result

        # Step 2: Save to knowledge directory
        try:
            self._save_content(source, text, source_type)
            result.content_saved = True
        except Exception as e:
            result.errors.append(f"Save failed: {e}")

        # Step 3: Extract entities with spaCy
        if self.nlp:
            entities = self._extract_entities(text)
            if self.kb:
                for ent in entities:
                    try:
                        await self.kb.upsert_entity(ent)
                        result.entities_extracted += 1
                    except Exception:
                        pass

        # Step 4: Save raw markdown for future reference
        self._save_markdown(source, text)

        return result

    async def _extract_text(self, source: str, source_type: str) -> str:
        """Extract plain text from a source."""
        if source_type == "url":
            return await self._fetch_url(source)
        elif source_type == "markdown":
            return Path(source).expanduser().read_text()
        elif source_type == "pdf":
            return self._extract_pdf(source)
        elif source_type in ("docx", "pptx", "xlsx"):
            return self._extract_office(source)
        return ""

    async def _fetch_url(self, url: str) -> str:
        """Fetch and extract content from a URL."""
        try:
            from minerva.search.backends import extract_bs4, extract_jina

            # Try Jina Reader first (better quality)
            content = await extract_jina(url)
            if content and len(content) > 200:
                return content
            # Fallback to BS4
            return await extract_bs4(url)
        except Exception:
            return ""

    def _extract_pdf(self, filepath: str, use_mineru: bool = False) -> str:
        """Extract text from a PDF file. Uses pdftotext by default, MinerU opt-in."""
        path = Path(filepath).expanduser()
        if not path.exists():
            return ""
        # MinerU only when explicitly enabled (opt-in, 2.3GB models)
        if use_mineru:
            try:
                from minerva.knowledge.mineru_adapter import (
                    is_available,
                    parse_to_text,
                )

                if is_available():
                    text = parse_to_text(str(path))
                    if text and len(text) > 50:
                        return text
            except Exception:
                pass
        # Default: pdftotext (lightweight, always available)
        try:
            import subprocess

            result = subprocess.run(
                ["pdftotext", "-layout", str(path), "-"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            return result.stdout if result.returncode == 0 else ""
        except Exception:
            return ""

    def _extract_office(self, filepath: str) -> str:
        """Extract text from Office documents via MinerU."""
        try:
            from minerva.knowledge.mineru_adapter import is_available, parse_to_text

            if is_available():
                return parse_to_text(str(Path(filepath).expanduser()))
        except Exception:
            pass
        return ""

    def _extract_entities(self, text: str) -> list:
        """Extract entities from text using spaCy."""
        from minerva.knowledge.store import Entity
        from minerva.shared import spacy_to_entity_type

        entities: list[Entity] = []
        doc = self.nlp(text[:10000])  # Limit to avoid memory issues
        seen_names = set()
        for ent in doc.ents:
            if ent.label_ in ("ORG", "PERSON", "GPE", "PRODUCT", "WORK_OF_ART", "EVENT") and ent.text not in seen_names:
                seen_names.add(ent.text)
                entities.append(
                    Entity(
                        id=f"ingest-{len(entities)}-{ent.label_}",
                        type=spacy_to_entity_type(ent.label_),
                        name=ent.text,
                        confidence="MEDIUM",
                        source_ids=[f"ingested:{ent.text}"],
                    )
                )
        return entities

    @staticmethod
    def _spacy_to_entity_type(label: str) -> str:
        from minerva.shared import spacy_to_entity_type as convert

        return convert(label)

    def _save_content(self, source: str, text: str, source_type: str) -> None:
        """Save raw extracted text."""
        slug = source.replace("/", "-").replace(":", "-")[:60]
        path = self.report_dir / f"{slug}.txt"
        path.write_text(text[:50000])

    def _save_markdown(self, source: str, text: str) -> None:
        """Save as markdown for knowledge base."""
        slug = source.replace("/", "-").replace(":", "-")[:60]
        path = self.report_dir / f"{slug}.md"
        title = f"# Ingested: {source}\n\n"
        path.write_text(title + text[:50000])

    @staticmethod
    def _detect_type(source: str) -> str:
        if source.startswith(("http://", "https://")):
            return "url"
        if source.endswith(".md"):
            return "markdown"
        if source.endswith(".pdf"):
            return "pdf"
        if source.endswith((".docx", ".pptx", ".xlsx")):
            return source.split(".")[-1]  # docx/pptx/xlsx → MinerU
        return "url"  # Default: try URL
