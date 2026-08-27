from __future__ import annotations

import logging
from typing import Any

_log = logging.getLogger(__name__)


class GenesisCallHandler:
    """Handles the "genesis" domain calls.

    Responsibilities (SRP): genesis/archetype distillation only.
    Extracted from ExecutionCoordinator._handle_genesis_call().
    """

    async def handle(self, resource: str, action: str, params: dict[str, Any] | None) -> dict[str, Any]:
        """Bridge to D-Genesis evolution forge."""
        try:
            global_forge = __import__(
                "organs.D_Genesis.organs.evolution_forge",
                fromlist=["global_forge"],
            ).global_forge
            return global_forge._handle_archetype_distill(params or {})
        except (ImportError, AttributeError) as e:
            _log.error("%s: %s", type(e).__name__, e)
            return {"status": "error", "message": f"Genesis bridge error: {e!s}"}
