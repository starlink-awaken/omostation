from __future__ import annotations

"""
HTML Content Extractor - Extracts structured knowledge from HTML

Extracted from SharedBrain D_Harvest → minerva.
"""
import re
from dataclasses import dataclass
from html.parser import HTMLParser

from minerva.extractors.base import IContentExtractor, StructuredKnowledge
from minerva.sources.connectors import RawContent


@dataclass
class ExtractionConfig:
    """HTML extraction configuration"""

    min_content_length: int = 50
    max_content_length: int = 100000
    strip_tags: bool = True
    preserve_structure: bool = False


class TextExtractor(HTMLParser):
    """Extracts visible text from HTML"""

    SKIP_TAGS = frozenset({"script", "style", "noscript", "iframe", "svg"})

    def __init__(self) -> None:
        super().__init__()
        self.text_parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self.SKIP_TAGS:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in self.SKIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0:
            text = data.strip()
            if text:
                self.text_parts.append(text)

    def get_text(self) -> str:
        """Return extracted text"""
        text = " ".join(self.text_parts)
        # Normalize whitespace
        text = re.sub(r"\s+", " ", text)
        return text.strip()


class HtmlContentExtractor(IContentExtractor):
    """Extracts structured knowledge from HTML with adaptive parsing"""

    def __init__(self, config: ExtractionConfig | None = None) -> None:
        self.config = config or ExtractionConfig()

    async def extract(self, raw: RawContent) -> list[StructuredKnowledge]:  # type: ignore[override]
        """Extract structured knowledge from HTML content"""
        # Decode bytes if needed
        if isinstance(raw.data, bytes):
            try:
                html = raw.data.decode("utf-8")
            except UnicodeDecodeError:
                # Fallback to latin-1
                html = raw.data.decode("latin-1", errors="replace")
        else:
            html = raw.data

        # Extract text using HTML parser
        parser = TextExtractor()
        parser.feed(html)
        body = parser.get_text()

        # Validate content length
        if len(body) < self.config.min_content_length:
            raise ValueError(f"Content too short: {len(body)} < {self.config.min_content_length}")

        if len(body) > self.config.max_content_length:
            # Truncate if too long
            body = body[: self.config.max_content_length]

        # Extract title from HTML or use URL
        title = self._extract_title(html, raw.uri)

        return [
            StructuredKnowledge(
                title=title,
                body=body,
                uri=raw.uri,
                metadata={
                    "content_type": raw.content_type,
                    "original_length": len(html),
                    "extracted_length": len(body),
                    "extraction_method": "html_text_extractor",
                },
            )
        ]

    def _extract_title(self, html: str, fallback_uri: str) -> str:
        """Extract title from HTML or generate from URI"""
        # Try to extract from <title> tag
        title_match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
        if title_match:
            title = title_match.group(1).strip()
            # Decode HTML entities
            title = re.sub(r"<[^>]+>", "", title)
            title = re.sub(r"\s+", " ", title).strip()
            if title and len(title) > 3:
                return title

        # Try to extract from <h1> tag
        h1_match = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.IGNORECASE | re.DOTALL)
        if h1_match:
            title = h1_match.group(1).strip()
            title = re.sub(r"<[^>]+>", "", title)
            title = re.sub(r"\s+", " ", title).strip()
            if title and len(title) > 3:
                return title

        # Fallback: generate from URI
        return self._title_from_uri(fallback_uri)

    def _title_from_uri(self, uri: str) -> str:
        """Generate a title from URI"""
        # Remove protocol and path
        parts = uri.split("/")
        if len(parts) > 1:
            last_part = parts[-1]
            # Remove file extension and query params
            last_part = last_part.split(".")[0].split("?")[0]
            if last_part:
                # Convert hyphens and underscores to spaces
                title = last_part.replace("-", " ").replace("_", " ")
                title = re.sub(r"\s+", " ", title).strip().title()
                if title:
                    return title

        # Final fallback: use domain
        from urllib.parse import urlparse

        parsed = urlparse(uri)
        return parsed.netloc or "Untitled Content"
