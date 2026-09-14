"""
Mem0 Adapter for KOS
====================
Provides a dual-track memory pipeline interface wrapping Mem0.
Implemented for Phase 1 decoupling and memory engine evaluation.

.. deprecated:: T3-03 (2026-08-08)
   Superseded by ``mos.adapters.mem0_shadow.Mem0ShadowAdapter``.
   mem0ai moved to optional dependency. New code MUST use MOS.
"""

import logging
import warnings
from typing import Any, cast

logger = logging.getLogger(__name__)
warnings.warn(
    "kos.adapters.mem0_adapter is deprecated (T3-03). Use mos.adapters.mem0_shadow instead.",
    DeprecationWarning,
    stacklevel=2,
)

try:
    from mem0 import Memory
except ImportError:
    Memory = None
    logger.warning("mem0ai is not installed. Mem0Adapter will be disabled.")


class Mem0Adapter:
    """Adapter for Mem0 memory engine for dual-track writing."""

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self.enabled = Memory is not None
        if self.enabled:
            try:
                # We use local configuration for Mem0 if not specified
                # e.g., storing vectors in a local sqlite/qdrant
                if not self.config:
                    self.config = {
                        "vector_store": {
                            "provider": "qdrant",
                            "config": {
                                "host": "localhost",
                                "port": 6333,
                            },
                        }
                    }
                self.memory = Memory.from_config(self.config)  # type: ignore[reportOptionalMemberAccess]
            except Exception as e:
                logger.error(f"Failed to initialize Mem0: {e}")
                self.enabled = False
                self.memory = None
        else:
            self.memory = None

    def add_memory(self, text: str, user_id: str, metadata: dict[str, Any] | None = None) -> None:
        if not self.enabled or not self.memory:
            return
        try:
            self.memory.add(text, user_id=user_id, metadata=metadata)
        except Exception as e:
            logger.error(f"Mem0 add_memory failed: {e}")

    def search_memory(self, query: str, user_id: str, limit: int = 5) -> list[dict[str, Any]]:
        if not self.enabled or not self.memory:
            return []
        try:
            return cast("list[dict[str, Any]]", self.memory.search(query, user_id=user_id, limit=limit))
        except Exception as e:
            logger.error(f"Mem0 search_memory failed: {e}")
            return []

    def get_all(self, user_id: str) -> list[dict[str, Any]]:
        if not self.enabled or not self.memory:
            return []
        try:
            return cast("list[dict[str, Any]]", self.memory.get_all(user_id=user_id))
        except Exception as e:
            logger.error(f"Mem0 get_all failed: {e}")
            return []

    def history(self, memory_id: str) -> list[dict[str, Any]]:
        if not self.enabled or not self.memory:
            return []
        try:
            return cast("list[dict[str, Any]]", self.memory.history(memory_id))
        except Exception as e:
            logger.error(f"Mem0 history failed: {e}")
            return []


# Global singleton for dual-track usage
mem0_adapter = Mem0Adapter()
