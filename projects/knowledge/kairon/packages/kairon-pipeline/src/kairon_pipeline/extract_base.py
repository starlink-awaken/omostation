from __future__ import annotations

"""
Base extraction models for the D-Harvest pipeline.

Defines ``StructuredKnowledge`` — the canonical output model produced by
all extractors and consumed by the quality gate and orchestrator.
"""

from typing import Any


class StructuredKnowledge:
    """Canonical output of a content extractor.

    Parameters
    ----------
    uri:
        Source URI of the extracted content.
    title:
        Extracted title / headline.
    body:
        Extracted text body.
    metadata:
        Arbitrary key-value pairs attached by the extractor.
    """

    def __init__(
        self,
        uri: str,
        title: str,
        body: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.uri = uri
        self.title = title
        self.body = body
        self.metadata = metadata or {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "uri": self.uri,
            "title": self.title,
            "body": self.body,
            "metadata": self.metadata,
        }
