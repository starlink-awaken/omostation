from __future__ import annotations

from pathlib import Path

from omo.omo_metrics import write_worker_utilization_summary


def test_write_worker_utilization_summary_accepts_multi_document_dispatch_yaml(
    tmp_path: Path,
) -> None:
    dispatch = tmp_path / ".omo" / "workers" / "runs" / "worker-a-dispatch.yaml"
    dispatch.parent.mkdir(parents=True, exist_ok=True)
    dispatch.write_text(
        "---\nstatus: active\nowner: runtime\n---\n---\n"
        "worker_id: worker-a\n"
        "dispatch_state: completed\n"
        "launched_at: 2026-06-23T10:00:00Z\n"
        "handoff:\n"
        "  output_summary_ref: .omo/_knowledge/summaries/worker-a.md\n"
        "reclaim:\n"
        "  successor_dispatch_id: worker-a-next\n",
        encoding="utf-8",
    )

    output_ref = write_worker_utilization_summary(tmp_path)
    output_path = tmp_path / output_ref
    content = output_path.read_text(encoding="utf-8")

    assert output_path.exists()
    assert "## worker-a" in content
    assert "- dispatches: 1" in content
    assert "- completed: 1" in content
    assert "- review_notes: 1" in content
    assert "- handoffs_out: 1" in content
