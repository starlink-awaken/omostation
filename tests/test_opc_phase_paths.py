from __future__ import annotations

from pathlib import Path

from omo.opc_phase_paths import load_opc_phase_task


def test_load_opc_phase_task_uses_shared_yaml_loader(tmp_path: Path) -> None:
    task_path = tmp_path / ".omo" / "tasks" / "planned" / "OPC-P5.yaml"
    task_path.parent.mkdir(parents=True, exist_ok=True)
    task_path.write_text(
        "---\nid: OPC-P5\nstatus: candidate\n---\nowner: reviewer\n",
        encoding="utf-8",
    )

    payload = load_opc_phase_task(tmp_path, "OPC-P5")

    assert payload["id"] == "OPC-P5"
    assert payload["status"] == "candidate"
    assert payload["owner"] == "reviewer"
