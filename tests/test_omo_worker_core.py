from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from omo.omo_worker_core import _find_task_file, _launch_worker_from_prompt


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


def test_prompt_launcher_keeps_output_and_raises_on_nonzero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prompt = tmp_path / "prompt.md"
    stdout = tmp_path / "stdout.log"
    prompt.write_text("do work", encoding="utf-8")
    registry = {
        "workers": [
            {
                "id": "worker-a",
                "enabled": True,
                "admission_state": "admitted",
                "transports": {"cli_prompt": {"command": 'worker-a "{prompt}"'}},
            }
        ]
    }
    monkeypatch.setattr(
        "omo.omo_worker_core.subprocess.run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess(
            ["worker-a"], 4, stdout="partial\n", stderr="failed\n"
        ),
    )

    with pytest.raises(RuntimeError, match="worker launch failed.*returncode=4"):
        _launch_worker_from_prompt(
            tmp_path, registry, "worker-a", "cli_prompt", prompt, stdout
        )

    assert stdout.read_text(encoding="utf-8") == "partial\nfailed\n"
