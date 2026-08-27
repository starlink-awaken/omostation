from __future__ import annotations

import importlib
import logging
from typing import Any

_log = logging.getLogger(__name__)


class EconomyCallHandler:
    """Handles the "economy" domain calls.

    Responsibilities (SRP): economy/ledger routing only.
    Extracted from ExecutionCoordinator._handle_economy_call().
    """

    async def handle(self, resource: str, action: str, params: dict[str, Any] | None) -> dict[str, Any]:
        """Dispatch economy calls to the appropriate ledger or reputation handler."""
        try:
            if resource == "ledger":
                return await self._handle_ledger(action, params)
            elif resource == "reputation":
                return await self._handle_reputation(action, params)
            return {
                "status": "error",
                "message": f"Unknown economy resource: {resource}",
            }
        except (ImportError, TypeError, ValueError, AttributeError) as e:
            _log.error("%s: %s", type(e).__name__, e)
            return {"status": "error", "message": f"Economy bridge error: {e!s}"}

    async def _handle_ledger(self, action: str, params: dict[str, Any] | None) -> dict[str, Any]:
        try:
            ledger_module = importlib.import_module("organs.D_Economy.organs.energy_ledger")
            ledger_cls = ledger_module.Ledger
        except (ImportError, ModuleNotFoundError, AttributeError):
            raise
        return ledger_cls.call(action, params)

    async def _handle_reputation(self, action: str, params: dict[str, Any] | None) -> dict[str, Any]:
        if action == "feedback":
            node_id = (params or {}).get("node_id")
            is_positive = (params or {}).get("is_positive", True)
            if not node_id:
                return {"status": "error", "message": "node_id required for feedback"}

            try:
                reputation_module = importlib.import_module("organs.D_Economy.organs.reputation_ledger")
                rep_ledger = reputation_module.ReputationLedger()
            except (ImportError, ModuleNotFoundError, AttributeError):
                raise
            new_rep = rep_ledger.apply_feedback(node_id, is_positive)
            return {"status": "success", "new_reputation": new_rep}

        return {"status": "error", "message": f"Unknown reputation action: {action}"}
