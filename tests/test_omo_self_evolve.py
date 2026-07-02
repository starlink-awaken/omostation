from __future__ import annotations

import json
from pathlib import Path

from omo.omo_self_evolve import (
    write_planned_self_evolution_tasks,
    write_self_evolve_summary,
)


def test_write_self_evolve_outputs(tmp_path: Path) -> None:
    tasks = [
        {
            "id": "OPC-P6-SELF-EVOLUTION-nop-1",
            "title": "No-op",
            "source": "drift:none",
            "drift_ref": "runtime/omo/_control/evolution/drift/2026-06-20.json",
            "approval_required": True,
            "human_approval_required": True,
            "approval_state": "awaiting_human",
            "loop_history_ref": "runtime/omo/_control/evolution/loop/history.json",
            "latest_week": "2026-W25",
        }
    ]
    paths = write_planned_self_evolution_tasks(tmp_path, tasks, "2026-06-20T00:00:00Z")
    summary_path = write_self_evolve_summary(
        tmp_path,
        {
            "generated_at": "2026-06-20T00:00:00Z",
            "tasks_emitted": 1,
            "tasks_written": 1,
            "tasks": [{"id": tasks[0]["id"], "approval_required": True}],
            "paths": [str(paths[0].relative_to(tmp_path))],
        },
        "2026-06-20T00:00:00Z",
    )

    assert len(paths) == 1
    assert paths[0].exists()
    content = paths[0].read_text(encoding="utf-8")
    assert "status: candidate" in content
    assert "human_approval_required: true" in content
    assert "approval_required: true" in content
    assert json.loads(summary_path.read_text(encoding="utf-8"))["tasks_written"] == 1
