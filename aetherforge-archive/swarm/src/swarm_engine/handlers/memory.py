from __future__ import annotations

import logging
from typing import Any

_log = logging.getLogger(__name__)


class MemoryCallHandler:
    """Handles the "memory" domain calls.

    Responsibilities (SRP): memory API bridge only.
    Extracted from ExecutionCoordinator._handle_memory_call().
    """

    async def handle(self, resource: str, action: str, params: dict[str, Any] | None) -> dict[str, Any]:
        """Bridge to D-Memory unified API."""
        try:
            memory_api_module = __import__(
                "organs.D_Memory.organs.unified_memory_api",
                fromlist=["UnifiedMemoryAPI", "get_default_unified_memory_api"],
            )

            handler_action = action or resource

            try:
                memory_ctrl = __import__(
                    "organs.D_Memory.organs.main_controller",
                    fromlist=["ctrl"],
                ).ctrl
                return await memory_ctrl.call(handler_action, params or {})
            except (ImportError, AttributeError):
                api = memory_api_module.get_default_unified_memory_api()
                return await api.call(handler_action, params or {})

        except (TypeError, ValueError, AttributeError, ImportError) as e:
            _log.error("%s: %s", type(e).__name__, e)
            return {"status": "error", "message": f"Memory bridge error: {e!s}"}
