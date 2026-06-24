from __future__ import annotations

from pathlib import Path

from omo.omo_handoff_index import write_handoff_index


def test_write_handoff_index_accepts_multi_document_yaml(tmp_path: Path) -> None:
    task_dir = tmp_path / ".omo" / "tasks" / "active"
    runs_dir = tmp_path / ".omo" / "workers" / "runs"
    task_dir.mkdir(parents=True, exist_ok=True)
    runs_dir.mkdir(parents=True, exist_ok=True)
    (tmp_path / ".omo" / "evidence" / "handoffs").mkdir(parents=True, exist_ok=True)

    (task_dir / "task.yaml").write_text(
        "---\nstatus: active\nowner: governance\n---\n---\n"
        "id: TASK-HANDOFF\n"
        "handoff_refs:\n"
        "  - .omo/workers/runs/TASK-HANDOFF-envelope.yaml\n"
        "run_ref: .omo/workers/runs/TASK-HANDOFF-dispatch.yaml\n"
        "review_ref: .omo/workers/runs/TASK-HANDOFF-review.md\n",
        encoding="utf-8",
    )
    (runs_dir / "TASK-HANDOFF-dispatch.yaml").write_text(
        "---\nstatus: active\nowner: runtime\n---\n---\n"
        "task_id: TASK-HANDOFF\n"
        "dispatch_state: completed\n"
        "execution:\n"
        "  checkpoint_refs:\n"
        "    - .omo/workers/runs/TASK-HANDOFF-checkpoint.md\n"
        "handoff:\n"
        "  output_summary_ref: .omo/_knowledge/summaries/TASK-HANDOFF.md\n"
        "reclaim:\n"
        "  note_ref: .omo/workers/runs/TASK-HANDOFF-reclaim.md\n",
        encoding="utf-8",
    )
    (runs_dir / "TASK-HANDOFF-envelope.yaml").write_text(
        "---\nstatus: active\nowner: runtime\n---\n---\n"
        "inputs:\n"
        "  prior_evidence:\n"
        "    - .omo/_knowledge/audits/evidence.md\n",
        encoding="utf-8",
    )

    output_ref = write_handoff_index(tmp_path, "TASK-HANDOFF")
    content = (tmp_path / output_ref).read_text(encoding="utf-8")

    assert "TASK-HANDOFF-dispatch.yaml" in content
    assert ".omo/_knowledge/audits/evidence.md" in content
