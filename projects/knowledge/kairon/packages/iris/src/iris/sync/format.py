"""Format converter: Obsidian Markdown ↔ WPS Note XML.

Rules for Markdown → XML:
  - `# Heading` → `<h1>Heading</h1>`
  - `## Heading` → `<h2>Heading</h2>`
  - Plain text → `<p>text</p>`
  - Blank lines separate paragraphs
  - List items → `<p>- item</p>` (no native list support in WPS)
  - Frontmatter (---...---) is stripped/ignored

Rules for XML → Markdown:
  - `<h1>Title</h1>` → `# Title`
  - `<p>Content</p>` → `Content`
  - Strip all XML tags, keep plain text
  - Blocks separated by blank lines
"""

from __future__ import annotations

import re
from typing import Any


class FormatConverter:
    """Converts between Obsidian Markdown and WPS Note XML formats."""

    def markdown_to_xml(self, md: str) -> str:
        """Convert Obsidian Markdown to WPS Note XML.

        Strips YAML frontmatter, converts headings and paragraphs to XML.
        """
        # Remove YAML frontmatter
        body = self._strip_frontmatter(md)

        # Split into blocks by double newlines (or single newlines
        # after heading lines since WPS treats each heading as block)
        blocks = self._split_blocks(body)

        xml_parts: list[str] = []
        for block in blocks:
            block = block.strip()
            if not block:
                continue

            # Check if it's a heading
            heading_match = re.match(r"^(#{1,6})\s+(.+)$", block, re.MULTILINE)
            if heading_match:
                level = len(heading_match.group(1))
                text = self._escape_xml(heading_match.group(2).strip())
                xml_parts.append(f"<h{level}>{text}</h{level}>")
                continue

            # Otherwise treat as paragraph
            text = self._escape_xml(block)
            xml_parts.append(f"<p>{text}</p>")

        return "\n".join(xml_parts) if xml_parts else "<p></p>"

    def xml_to_markdown(self, xml: str) -> str:
        """Convert WPS Note XML to Obsidian Markdown.

        Converts XML tags back to Markdown headings and paragraphs.
        """
        if not xml or not xml.strip():
            return ""

        # Split into individual XML blocks
        # Pattern matches <tag>content</tag> including nested tags
        blocks = re.findall(r"<(h[1-6]|p)>(.*?)</\1>", xml, re.DOTALL)

        md_parts: list[str] = []
        for tag, content in blocks:
            content = content.strip()
            # Unescape XML entities
            content = self._unescape_xml(content)

            if tag.startswith("h"):
                level = tag[1]
                md_parts.append(f"{'#' * int(level)} {content}")
            else:
                md_parts.append(content)

        return "\n\n".join(md_parts)

    def frontmatter_to_dict(self, md: str) -> dict[str, Any]:
        """Parse YAML frontmatter from Markdown into a dict.

        Returns:
            Dict with keys: title, tags, created_at, updated_at, iris_id, aliases
        """
        result: dict[str, Any] = {
            "title": "",
            "tags": [],
            "created_at": "",
            "updated_at": "",
            "iris_id": "",
            "aliases": [],
        }

        fm_match = re.match(r"^---\n(.*?)\n---", md, re.DOTALL)
        if not fm_match:
            return result

        fm_text = fm_match.group(1)

        # Title
        title_match = re.search(r"^title:\s*(.+)$", fm_text, re.MULTILINE)
        if title_match:
            result["title"] = title_match.group(1).strip().strip("\"'")

        # Tags (inline: tags: [a, b] or block: tags:\n  - a)
        tag_match = re.search(r"tags:\s*\[(.*?)\]", fm_text)
        if tag_match:
            result["tags"] = [t.strip().strip("\"'") for t in tag_match.group(1).split(",")]
        else:
            block_match = re.search(r"tags:\s*\n((?:\s+-\s+.*\n?)+)", fm_text)
            if block_match:
                result["tags"] = [t.strip().lstrip("- ") for t in block_match.group(1).split("\n") if t.strip()]

        # Created / date
        for key in ("created_at", "created", "date"):
            date_match = re.search(rf"{key}:\s*['\"]?(\d{{4}}-\d{{2}}-\d{{2}})", fm_text)
            if date_match:
                result["created_at"] = date_match.group(1)
                break

        # Updated
        upd_match = re.search(r"updated_at:\s*['\"]?(\d{{4}}-\d{{2}}-\d{{2}})", fm_text)
        if upd_match:
            result["updated_at"] = upd_match.group(1)

        # Iris ID
        iris_match = re.search(r"iris_id:\s*(.+)", fm_text)
        if iris_match:
            result["iris_id"] = iris_match.group(1).strip()

        # Aliases
        alias_match = re.search(r"aliases:\s*\[(.*?)\]", fm_text)
        if alias_match:
            result["aliases"] = [a.strip().strip("\"'") for a in alias_match.group(1).split(",")]
        else:
            block_match = re.search(r"aliases:\s*\n((?:\s+-\s+.*\n?)+)", fm_text)
            if block_match:
                result["aliases"] = [a.strip().lstrip("- ") for a in block_match.group(1).split("\n") if a.strip()]

        return result

    def dict_to_frontmatter(self, data: dict[str, Any]) -> str:
        """Generate a YAML frontmatter string from a dict.

        Common keys: title, tags, created_at, updated_at, iris_id, status.
        """
        lines = ["---"]
        if data.get("title"):
            lines.append(f"title: {self._yaml_escape(data['title'])}")
        if data.get("status"):
            lines.append(f"status: {data['status']}")
        if data.get("tags"):
            lines.append("tags:")
            for t in data["tags"]:
                lines.append(f"  - {self._yaml_escape(t)}")
        if data.get("created_at"):
            lines.append(f"created_at: {data['created_at']}")
        if data.get("updated_at"):
            lines.append(f"updated_at: {data['updated_at']}")
        if data.get("iris_id"):
            lines.append(f"iris_id: {data['iris_id']}")
        lines.append("---")
        return "\n".join(lines)

    # ── Internal helpers ──────────────────────────────────────────

    def _strip_frontmatter(self, md: str) -> str:
        """Remove YAML frontmatter (--- ... ---) from content."""
        return re.sub(r"^---\n.*?\n---\n*", "", md, flags=re.DOTALL)

    def _split_blocks(self, text: str) -> list[str]:
        """Split text into logical blocks separated by blank lines.

        A heading line and its following lines are kept together
        only if they're on the same paragraph. In Markdown, a heading
        ends a paragraph, so headings are treated as separate blocks.
        """
        # Normalize line endings
        text = text.replace("\r\n", "\n").replace("\r", "\n")

        # Split by blank lines (two or more consecutive newlines)
        blocks = re.split(r"\n\n+", text)
        return [b.strip() for b in blocks if b.strip()]

    def _escape_xml(self, text: str) -> str:
        """Escape XML special characters."""
        text = text.replace("&", "&amp;")
        text = text.replace("<", "&lt;")
        text = text.replace(">", "&gt;")
        text = text.replace('"', "&quot;")
        return text

    def _unescape_xml(self, text: str) -> str:
        """Unescape XML special characters back to plain text."""
        text = text.replace("&lt;", "<")
        text = text.replace("&gt;", ">")
        text = text.replace("&quot;", '"')
        text = text.replace("&amp;", "&")
        return text

    def _yaml_escape(self, value: str) -> str:
        """Escape a YAML string value."""
        if not value:
            return '""'
        if any(c in value for c in ":#{}[]&*!|>%@`,"):
            return f'"{value}"'
        return value
