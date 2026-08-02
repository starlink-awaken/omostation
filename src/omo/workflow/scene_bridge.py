"""Scene binding bridge - connects External Connection Fabric scene context to Workflow Mesh.

Phase 4 of the Mesh Bridge strategy: ensures WorkflowRequested events carry
scene_binding (scene_id, journey_id, outcome_metric) so the Mesh can correlate
executions with business scenes from the External Connection Fabric.

The bridge extracts scene_binding from:
1. Explicit scene_binding in workflow context/params
2. SceneCard/SceneBinding objects passed through the workflow lifecycle
3. Workflow definitions that declare scene_binding metadata

If no scene context is available, events are emitted without scene_binding
(standard Mesh behavior - scene_binding is optional but recommended).
"""
from __future__ import annotations

from typing import Any


def extract_scene_binding(
    context: dict[str, Any] | None = None,
    workflow: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
) -> dict[str, str] | None:
    """Extract scene_binding from available context sources.

    Returns a dict with scene_id, journey_id, outcome_metric if all present,
    or None if scene context is not available.

    Priority:
    1. Explicit scene_binding in params
    2. scene_binding in workflow definition metadata
    3. scene_id/journey_id/outcome_metric in context
    """
    # 1. Check params for explicit scene_binding
    if params and isinstance(params.get("scene_binding"), dict):
        binding = params["scene_binding"]
        result = _validate_binding(binding)
        if result:
            return result

    # 2. Check workflow definition for scene_binding metadata
    if workflow:
        meta = workflow.get("metadata", {})
        if isinstance(meta, dict) and isinstance(meta.get("scene_binding"), dict):
            binding = meta["scene_binding"]
            result = _validate_binding(binding)
            if result:
                return result

    # 3. Check context for individual fields
    if context:
        binding = {
            "scene_id": str(context.get("scene_id", "")).strip(),
            "journey_id": str(context.get("journey_id", "")).strip(),
            "outcome_metric": str(context.get("outcome_metric", "")).strip(),
        }
        result = _validate_binding(binding)
        if result:
            return result

    return None


def _validate_binding(binding: dict[str, Any]) -> dict[str, str] | None:
    """Validate that binding has all required non-empty fields."""
    required = {"scene_id", "journey_id", "outcome_metric"}
    if not all(k in binding for k in required):
        return None
    result = {k: str(binding[k]).strip() for k in required}
    if not all(result.values()):
        return None
    return result


def inject_scene_binding(
    payload: dict[str, Any],
    scene_binding: dict[str, str] | None,
) -> dict[str, Any]:
    """Inject scene_binding into event payload if available.

    Returns the payload with scene_binding added (or unchanged if None).
    """
    if scene_binding:
        payload = dict(payload)
        payload["scene_binding"] = scene_binding
    return payload
