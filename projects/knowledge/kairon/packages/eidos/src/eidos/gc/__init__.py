"""GC Engine — garbage collection, memory excretion, distillation."""

from eidos.gc.archiver import (
    ArchiveEntry,
    ArchiveManager,
    ArchivePolicy,
    StorageTier,
    TieredStorage,
)
from eidos.gc.distillation import DistillationEngine
from eidos.gc.excretion import MemoryExcretionPipeline
from eidos.gc.gc_core import GCEngine, GCStats
from eidos.gc.lifecycle import DecayConfig, LifecycleManager, LifecycleRecord
from eidos.gc.retention import RetentionPolicy

__all__ = (
    "ArchiveEntry",
    "ArchiveManager",
    "ArchivePolicy",
    "DecayConfig",
    "DistillationEngine",
    "GCEngine",
    "GCStats",
    "LifecycleManager",
    "LifecycleRecord",
    "MemoryExcretionPipeline",
    "RetentionPolicy",
    "StorageTier",
    "TieredStorage",
)
