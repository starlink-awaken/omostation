#!/usr/bin/env python3
"""Scene Card → OMO Task 映射桥接.

When an intent is approved, this bridge creates an OMO Task with the
scene binding contract embedded, enabling traceability from business
scenario to execution outcome.

SSOT:  ecos/src/ecos/ssot/registry/scene-binding-contract.yaml
Bridge: bin/ssot/scene-card-task-bridge.py
"""

from __future__ import annotations

import importlib.util
import json
import sys
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class SceneBinding:
    binding_id: str = ""
    scene_id: str = ""
    journey_id: str = ""
    intent_id: str = ""
    task_id: str = ""
    outcome_metric: str = ""
    created_at: str = ""
    status: str = "active"


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def _load_decision_inbox_engine(workspace_root: Path):
    engine_path = workspace_root / "bin" / "ssot" / "scene-card-decision-inbox.py"
    spec = importlib.util.spec_from_file_location("scene_card_task_bridge", str(engine_path))
    if spec is None or spec.loader is None:
        raise ImportError("scene-card-decision-inbox.py is unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _bindings_path(workspace_root: Path) -> Path:
    p = workspace_root / ".omo" / "_bindings"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _binding_path(workspace_root: Path, binding_id: str) -> Path:
    return _bindings_path(workspace_root) / f"{binding_id}.json"


def save_binding(workspace_root: Path, binding: SceneBinding) -> None:
    p = _binding_path(workspace_root, binding.binding_id)
    p.write_text(json.dumps(asdict(binding), indent=2, ensure_ascii=False))


def load_binding(workspace_root: Path, binding_id: str) -> SceneBinding | None:
    p = _binding_path(workspace_root, binding_id)
    if not p.exists():
        return None
    data = json.loads(p.read_text())
    return SceneBinding(**data)


def list_bindings(workspace_root: Path) -> list[SceneBinding]:
    p = _bindings_path(workspace_root)
    bindings = []
    for f in sorted(p.glob("bind-*.json")):
        data = json.loads(f.read_text())
        bindings.append(SceneBinding(**data))
    return bindings


def approve_intent_and_create_task(
    workspace_root: Path,
    intent_id: str,
    outcome_metric: str = "",
    actor: str = "system",
) -> dict[str, Any]:
    """Approve an intent and create its OMO task binding.

    Flow:
      1. Update intent status to 'approved' in decision inbox
      2. Create a scene binding contract
      3. Record the binding in .omo/_bindings/

    Returns:
        Dict with binding_id, task_id, and status.
    """
    engine = _load_decision_inbox_engine(workspace_root)

    # Update intent status to approved
    intent = engine.update_intent_status(
        workspace_root,
        intent_id=intent_id,
        new_status="approved",
        actor=actor,
    )
    if intent is None:
        return {"ok": False, "error": f"Intent {intent_id} not found"}

    # Find the scene and journey for this intent
    scene_id = ""
    journey_id = ""
    scenes = engine.list_scenes(workspace_root)
    for scene in scenes:
        for journey in scene.journeys:
            for i in journey.intents:
                if i.id == intent_id:
                    scene_id = scene.id
                    journey_id = journey.id
                    break

    # Create binding
    binding_id = _new_id("bind")
    task_id = f"task-{uuid.uuid4().hex[:12]}"
    binding = SceneBinding(
        binding_id=binding_id,
        scene_id=scene_id,
        journey_id=journey_id,
        intent_id=intent_id,
        task_id=task_id,
        outcome_metric=outcome_metric or "verified_outcome",
        created_at=_now_iso(),
        status="active",
    )
    save_binding(workspace_root, binding)

    # Update intent with task_id
    engine.update_intent_status(
        workspace_root,
        intent_id=intent_id,
        new_status="task_created",
        task_id=task_id,
        actor=actor,
    )

    return {
        "ok": True,
        "binding_id": binding_id,
        "task_id": task_id,
        "scene_id": scene_id,
        "journey_id": journey_id,
        "intent_id": intent_id,
        "status": "task_created",
    }


def complete_task(
    workspace_root: Path,
    binding_id: str,
    outcome: str = "completed",
) -> dict[str, Any]:
    """Mark a scene binding as completed."""
    binding = load_binding(workspace_root, binding_id)
    if binding is None:
        return {"ok": False, "error": f"Binding {binding_id} not found"}

    binding.status = "completed"
    save_binding(workspace_root, binding)

    engine = _load_decision_inbox_engine(workspace_root)
    engine.update_intent_status(
        workspace_root,
        intent_id=binding.intent_id,
        new_status="done",
        actor="task_bridge",
    )

    return {
        "ok": True,
        "binding_id": binding_id,
        "task_id": binding.task_id,
        "status": "completed",
    }


def get_binding_status(workspace_root: Path, intent_id: str) -> dict[str, Any] | None:
    """Get the binding status for an intent."""
    bindings = list_bindings(workspace_root)
    for b in bindings:
        if b.intent_id == intent_id:
            return {
                "binding_id": b.binding_id,
                "task_id": b.task_id,
                "scene_id": b.scene_id,
                "intent_id": b.intent_id,
                "status": b.status,
                "created_at": b.created_at,
            }
    return None
