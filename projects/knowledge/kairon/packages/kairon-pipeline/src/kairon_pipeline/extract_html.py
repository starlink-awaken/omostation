from __future__ import annotations

"""
HTML content extractor for the D-Harvest pipeline.

Provides ``HtmlContentExtractor`` which converts raw HTML into one or more
``StructuredKnowledge`` items.
"""


from kairon_pipeline.extract_base import StructuredKnowledge
from kairon_pipeline.source_connectors import RawContent


class HtmlContentExtractor:
    """Extract structured knowledge from HTML content.

    This is a basic stub implementation that wraps the raw content as a
    single ``StructuredKnowledge`` item.  TODO: integrate with a real HTML
    parser (e.g. BeautifulSoup, trafilatura) for full extraction.
    """

    async def extract(
        self,
        content: RawContent | str,
    ) -> StructuredKnowledge | list[StructuredKnowledge]:
        """Extract structured knowledge from *content*.

        Parameters
        ----------
        content:
            Either a ``RawContent`` object or a plain HTML string.

        Returns
        -------
        StructuredKnowledge | list[StructuredKnowledge]
            A single item (or a list, for future multi-article support).
        """
        if isinstance(content, RawContent):
            html = content.data
            uri = content.uri
        else:
            html = content
            uri = "inline://html"

        # Basic title extraction from <title> tag
        title = ""
        if "<title>" in html and "</title>" in html:
            start = html.index("<title>") + len("<title>")
            end = html.index("</title>")
            title = html[start:end].strip()

        # Strip tags for body text (very basic)
        body = html
        for tag in ("<html>", "</html>", "<head>", "</head>", "<body>", "</body>"):
            body = body.replace(tag, "")

        return StructuredKnowledge(
            uri=uri,
            title=title or "Untitled",
            body=body,
            metadata={"source": "html_extractor", "content_type": "text/html"},
        )
