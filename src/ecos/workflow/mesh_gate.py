"""Mesh connection gate - verifies Workflow Mesh connectivity before admission.

Phase 3 of the Mesh Bridge strategy: makes Mesh connection a first-class
governance gate in the ECOS workflow execution pipeline.

Design:
- Runs after X1/X2 validation, before admission grant
- Default mode: warning only (non-blocking), events gracefully degrade
- Strict mode (ECOS_MESH_GATE_STRICT=1): blocks execution if Mesh unavailable
- Checks that the Mesh store can receive events (not just that it exists)
"""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger("ecos.workflow.mesh_gate")

MESH_GATE_VIOLATION_ID = "MESH-GATE-01"


def is_strict_mode() -> bool:
    """Check if mesh gate is in strict (blocking) mode."""
    return os.environ.get("ECOS_MESH_GATE_STRICT", "0").strip() == "1"


def check_mesh_connection() -> dict[str, Any]:
    """Check if Workflow Mesh store is connected and can receive events.

    Returns:
        dict with keys:
        - connected: bool
        - store_path: str | None
        - reason: str
        - strict: bool
    """
    from ecos.workflow.default_mesh_sink import _get_workflow_mesh_store

    store = _get_workflow_mesh_store()
    if store is None:
        return {
            "connected": False,
            "store_path": None,
            "reason": "OMO WorkflowMeshStore not found",
            "strict": is_strict_mode(),
        }

    try:
        store_path = getattr(store, "omo_dir", None)
        events = store.events()
        return {
            "connected": True,
            "store_path": str(store_path) if store_path else "unknown",
            "reason": f"Mesh store accessible ({len(events)} events)",
            "strict": is_strict_mode(),
        }
    except Exception as exc:
        return {
            "connected": False,
            "store_path": None,
            "reason": f"Mesh store error: {exc}",
            "strict": is_strict_mode(),
        }


def mesh_gate_check() -> list[dict]:
    """Run mesh connection gate check.

    Returns list of violations (empty if connected, or non-blocking warning
    if disconnected in default mode, or blocking error in strict mode).
    """
    result = check_mesh_connection()

    if result["connected"]:
        logger.debug("Mesh gate: connected (%s)", result["reason"])
        return []

    severity = "error" if result["strict"] else "warning"
    violation = {
        "id": MESH_GATE_VIOLATION_ID,
        "constraint": "MESH-GATE",
        "severity": severity,
        "message": f"Workflow Mesh not connected: {result['reason']}",
    }

    if result["strict"]:
        logger.warning("Mesh gate BLOCKED execution: %s", result["reason"])
    else:
        logger.info("Mesh gate warning (non-blocking): %s", result["reason"])

    return [violation]
