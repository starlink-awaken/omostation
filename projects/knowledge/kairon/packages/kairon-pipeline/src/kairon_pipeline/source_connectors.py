from __future__ import annotations

"""
Raw content model for the D-Harvest pipeline.

Provides ``RawContent`` — the universal carrier for unprocessed data
fetched from a source before extraction.
"""

from typing import Any


class RawContent:
    """Raw, unprocessed content fetched from a data source.

    Parameters
    ----------
    uri:
        Source URI (e.g. ``"https://example.com/doc"``).
    data:
        The raw content bytes or string.
    content_type:
        MIME type hint (e.g. ``"text/html"``, ``"application/json"``).
    metadata:
        Arbitrary key-value pairs from the fetch step.
    """

    def __init__(
        self,
        uri: str,
        data: str,
        content_type: str = "text/plain",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.uri = uri
        self.data = data
        self.content_type = content_type
        self.metadata = metadata or {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "uri": self.uri,
            "data": self.data,
            "content_type": self.content_type,
            "metadata": self.metadata,
        }
