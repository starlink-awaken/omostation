from __future__ import annotations

"""
内容提取器接口

Extracted from SharedBrain D_Harvest → minerva.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from minerva.sources.connectors import RawContent

utc = datetime.now(UTC)


@dataclass
class StructuredKnowledge:
    """结构化知识"""

    title: str
    body: str
    uri: str
    metadata: dict = field(default_factory=dict)
    visibility: str = "private"  # private, federated
    harvested_at: str = field(default_factory=lambda: utc.isoformat())


class IContentExtractor(ABC):
    """内容提取器接口"""

    @abstractmethod
    async def extract(self, content: RawContent) -> list[StructuredKnowledge]:
        """提取结构化知识"""
        pass
