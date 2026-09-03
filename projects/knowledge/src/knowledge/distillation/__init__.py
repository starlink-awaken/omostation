"""Knowledge Distillation and Proactive Consolidation Subsystem."""

from knowledge.distillation.conflict_resolver import ConflictResolutionProposal, ConflictResolver
from knowledge.distillation.engine import MemoryDistillationEngine

__all__ = [
    "ConflictResolver",
    "ConflictResolutionProposal",
    "MemoryDistillationEngine",
]
