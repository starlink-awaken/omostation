from __future__ import annotations

from pathlib import Path

import yaml
from omo.omo_audit_sync import FieldDiff, apply_diff


def test_apply_diff_uses_system_projection_broker(tmp_path: Path) -> None:
    system_path = tmp_path / ".omo" / "state" / "system.yaml"
    system_path.parent.mkdir(parents=True, exist_ok=True)
    system_path.write_text(
        'current_phase: 42\ncompleted_tasks: 0\nupdated_at: "2026-06-22T00:00:00Z"\n',
        encoding="utf-8",
    )

    rendered = apply_diff(
        [
            FieldDiff(
                field="completed_tasks",
                old_value="0",
                new_value=5,
                reason="actual state differs",
            )
        ],
        system_path,
        apply=True,
    )

    data = yaml.safe_load(system_path.read_text(encoding="utf-8"))
    assert data["completed_tasks"] == 5
    assert "completed_tasks: 5" in rendered
    artifact_dir = tmp_path / "runtime" / "omo" / "_delivery" / "ingress" / "state"
    assert any(
        path.name.startswith("system-projection-")
        for path in artifact_dir.glob("*.yaml")
    )
