from __future__ import annotations

from pathlib import Path

from .omo_shared import load_yaml

PHASE_TASK_IDS = {
    "P3": "OPC-P3-GATE-D-OPENING",
    "P4": "OPC-P4-MODEL-COMPUTE",
    "P5": "OPC-P5",
    "P6": "OPC-P6",
    "P7": "OPC-P7",
}


def resolve_opc_phase_task_path(workspace_root: Path, task_id: str) -> Path:
    candidates = [
        workspace_root / ".omo" / "tasks" / "planned" / f"{task_id}.yaml",
        workspace_root / ".omo" / "tasks" / "done" / f"{task_id}.yaml",
        workspace_root / ".omo" / "tasks" / "registry" / "done" / f"{task_id}.yaml",
    ]
    for path in candidates:
        if path.exists():
            return path
    raise FileNotFoundError(f"unable to resolve OPC phase task carrier for {task_id}")


def load_opc_phase_task(workspace_root: Path, task_id: str) -> dict:
    path = resolve_opc_phase_task_path(workspace_root, task_id)
    return load_yaml(path)
