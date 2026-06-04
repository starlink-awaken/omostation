from __future__ import annotations

from pathlib import Path

import yaml

from scripts.omo_skill import create_skill_task_packet, register_skill_manifest
from scripts.omo_task_schema import validate_task_file


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_register_skill_manifest_writes_truth_record(tmp_path: Path):
    manifest = register_skill_manifest(
        tmp_path,
        {
            "id": "skill.review.refresh",
            "title": "Review refresh skill",
            "worker_bridge": "mockworker",
            "source_docs": [".omo/plans/phase6-wave1-execution-plan.md"],
            "deliverables": [".omo/evidence/handoffs/review-refresh.md"],
            "allowed_write_paths": [".omo/evidence/handoffs/"],
            "risk_level": "L1",
            "allowed_operation_level": "L1",
        },
    )

    manifest_path = tmp_path / ".omo" / "_truth" / "task-center" / "skills" / "skill.review.refresh.yaml"
    assert manifest_path.exists()
    payload = _load_yaml(manifest_path)
    assert manifest["id"] == "skill.review.refresh"
    assert payload["worker_bridge"] == "mockworker"


def test_create_skill_task_packet_bridges_skill_to_worker_runtime(tmp_path: Path):
    register_skill_manifest(
        tmp_path,
        {
            "id": "skill.review.refresh",
            "title": "Review refresh skill",
            "worker_bridge": "mockworker",
            "source_docs": [".omo/plans/phase6-wave3-execution-plan.md"],
            "deliverables": [".omo/evidence/handoffs/review-refresh.md"],
            "allowed_write_paths": [".omo/evidence/handoffs/"],
            "risk_level": "L1",
            "allowed_operation_level": "L1",
        },
    )

    result = create_skill_task_packet(
        tmp_path,
        skill_id="skill.review.refresh",
        task_id="P6-G3-SKILL-FEDERATION-PACKET",
        title="Land the skill federation packet",
    )

    task_path = tmp_path / result["task_ref"]
    task = _load_yaml(task_path)
    assert task["id"] == "P6-G3-SKILL-FEDERATION-PACKET"
    assert task["status"] == "blocked"
    assert task["source_docs"] == [
        ".omo/plans/phase6-wave3-execution-plan.md",
        ".omo/_truth/task-center/skills/skill.review.refresh.yaml",
    ]
    assert task["worker_bridge"] == "mockworker"
    assert validate_task_file(task_path) == []
