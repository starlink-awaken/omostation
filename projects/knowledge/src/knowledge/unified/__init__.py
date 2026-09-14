"""Unified Memory Interface — bos://memory/unified single entry point.

Consolidates gbrain and kairon access paths into a single query/ingest/search
contract, eliminating redundant adapter stubs across both subsystems.
"""

from knowledge.unified.adapter_bridge import UnifiedMemoryBridge
from knowledge.unified.interface import UnifiedMemoryInterface

__all__ = ["UnifiedMemoryInterface", "UnifiedMemoryBridge"]
