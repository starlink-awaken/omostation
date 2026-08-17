"""文档分析器基类"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class DocumentAnalysis:
    path: Path
    format: str = "unknown"
    pages: int = 0
    word_count: int = 0
    sections: list[dict] = field(default_factory=list)
    tables: list[dict] = field(default_factory=list)
    entities: list[dict] = field(default_factory=list)
    relations: list[dict] = field(default_factory=list)
    error: str | None = None


class DocAnalyzer(ABC):
    @abstractmethod
    def analyze(self, path: Path) -> DocumentAnalysis: ...

    @abstractmethod
    def name(self) -> str: ...
