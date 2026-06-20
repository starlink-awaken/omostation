from __future__ import annotations

import importlib.util
from pathlib import Path


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "ecos"
    / "ssot"
    / "tools"
    / "mof-state-bridge.py"
)


def _load_module():
    spec = importlib.util.spec_from_file_location("mof_state_bridge", MODULE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_broker_imports_only_proposed_nodes(monkeypatch, tmp_path: Path) -> None:
    module = _load_module()
    calls: list[dict] = []

    def fake_create_planned_task(omo_dir, *, task_data, ingress_plane, source_ref, now=None):
        calls.append(
            {
                "omo_dir": omo_dir,
                "task_data": task_data,
                "ingress_plane": ingress_plane,
                "source_ref": source_ref,
            }
        )
        return task_data

    monkeypatch.setattr(module, "create_planned_task", fake_create_planned_task)

    diff = {
        "pairs": [
            {
                "omo_exists": False,
                "omo_id": "TASK-X",
                "m1_data": {
                    "id": "OMOTASK-TASK-X",
                    "status": "proposed",
                    "name": "Task X",
                    "description": "seed desc",
                    "priority": "P1",
                    "domain": "opc",
                    "properties": {"evidence": ["artifact-a"]},
                },
            }
        ],
        "m1_only": [],
        "omo_only": [],
        "drifts": [],
    }

    result = module._broker_import_m1_to_omo_candidates(diff, omo_dir=tmp_path / ".omo")

    assert result["blocked"] == []
    assert result["imported"] == [
        {
            "m1_id": "OMOTASK-TASK-X",
            "omo_id": "TASK-X",
            "target_ref": ".omo/tasks/planned/TASK-X.yaml",
        }
    ]
    assert len(calls) == 1
    assert calls[0]["ingress_plane"] == "projects/ecos:mof-state-bridge"
    assert calls[0]["source_ref"] == "ecos:mof-state-bridge:m1-to-omo:OMOTASK-TASK-X"
    assert calls[0]["task_data"]["status"] == "candidate"
    assert calls[0]["task_data"]["source_docs"] == [
        "projects/ecos/src/ecos/ssot/mof/m1/omo_layer/OMOTASK-TASK-X.yaml"
    ]
    assert calls[0]["task_data"]["entry_gate"] == ["M1_OMOTASK_BROKER_IMPORT"]


def test_broker_blocks_non_proposed_nodes(monkeypatch, tmp_path: Path) -> None:
    module = _load_module()
    calls: list[dict] = []

    def fake_create_planned_task(omo_dir, *, task_data, ingress_plane, source_ref, now=None):
        calls.append(task_data)
        return task_data

    monkeypatch.setattr(module, "create_planned_task", fake_create_planned_task)

    diff = {
        "pairs": [
            {
                "omo_exists": False,
                "omo_id": "TASK-DONE",
                "m1_data": {
                    "id": "OMOTASK-TASK-DONE",
                    "status": "done",
                    "name": "Task Done",
                },
            }
        ],
        "m1_only": [],
        "omo_only": [],
        "drifts": [],
    }

    result = module._broker_import_m1_to_omo_candidates(diff, omo_dir=tmp_path / ".omo")

    assert result["imported"] == []
    assert result["blocked"] == [
        {
            "m1_id": "OMOTASK-TASK-DONE",
            "omo_id": "TASK-DONE",
            "reason": "unsupported_m1_status:done",
            "target_ref": ".omo/tasks/planned/TASK-DONE.yaml",
        }
    ]
    assert calls == []
