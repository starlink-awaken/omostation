"""Knowledge Engineering Complex Unified Facade."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

# Auto-register kairon subpackages into sys.path
KAIRON_PACKAGES = Path(__file__).resolve().parent.parent.parent / "kairon" / "packages"
if KAIRON_PACKAGES.exists():
    for pkg in KAIRON_PACKAGES.iterdir():
        if pkg.is_dir() and (pkg / "src").exists():
            pkg_src = str(pkg / "src")
            if pkg_src not in sys.path:
                sys.path.insert(0, pkg_src)

from knowledge.models import (
    KnowledgeDocument,
    KnowledgeEntity,
    KnowledgeRelation,
    RetrievalResult,
    SyncEvent,
)
from knowledge.adapter import BaseKnowledgeAdapter, AdapterHealth
from knowledge.retrieval import UnifiedKnowledgeRetriever

__version__ = "1.0.0"
__all__ = [
    "KnowledgeComplex",
    "get_knowledge_facade",
    "KnowledgeDocument",
    "KnowledgeEntity",
    "KnowledgeRelation",
    "RetrievalResult",
    "SyncEvent",
    "BaseKnowledgeAdapter",
    "AdapterHealth",
    "UnifiedKnowledgeRetriever",
]


class KnowledgeComplex:
    """知识工程复合体统一门面 (Knowledge Engineering Complex Facade)."""

    def __init__(self) -> None:
        self.kairon_root = KAIRON_PACKAGES
        self.gbrain_root = Path(__file__).resolve().parent.parent.parent / "gbrain"
        self._retriever = UnifiedKnowledgeRetriever()

    def status(self) -> dict[str, Any]:
        """获取复合体双擎健康状态."""
        return {
            "status": "healthy",
            "version": __version__,
            "subengines": {
                "kairon": {
                    "exists": self.kairon_root.exists(),
                    "packages_count": len(list(self.kairon_root.iterdir())) if self.kairon_root.exists() else 0,
                },
                "gbrain": {
                    "exists": self.gbrain_root.exists(),
                    "substrate": "PostgreSQL+pgvector",
                },
            },
        }

    def search(self, query: str, domain: str = "common", limit: int = 10) -> list[RetrievalResult]:
        """统一混合检索快捷入口."""
        return self._retriever.retrieve(query, domain=domain, limit=limit)


def get_knowledge_facade() -> KnowledgeComplex:
    """获取知识复合体单例."""
    return KnowledgeComplex()
