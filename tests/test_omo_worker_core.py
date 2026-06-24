from __future__ import annotations

from pathlib import Path

from omo.omo_worker_core import _find_task_file


def test_find_task_file_accepts_multi_document_yaml(tmp_path: Path) -> None:
    active_dir = tmp_path / ".omo" / "tasks" / "active"
    active_dir.mkdir(parents=True, exist_ok=True)
    task_path = active_dir / "wave1.yaml"
    task_path.write_text(
        "---\nstatus: active\nowner: governance\n---\n---\n"
        "id: TASK-MULTI-DOC\n"
        "title: Multi doc task\n"
        "status: pending\n",
        encoding="utf-8",
    )

    resolved = _find_task_file(active_dir, "TASK-MULTI-DOC")

    assert resolved == task_path
