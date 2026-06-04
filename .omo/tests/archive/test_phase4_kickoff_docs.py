from __future__ import annotations

from pathlib import Path


OMO_ROOT = Path(__file__).resolve().parents[1]


def _read(rel_path: str) -> str:
    return (OMO_ROOT / rel_path).read_text(encoding="utf-8")


def test_phase4_roadmap_exists_with_worker_collab_focus():
    text = _read("plans/phase4-execution-roadmap.md")

    assert "# Phase 4 execution roadmap" in text
    assert "## Worker collaboration assessment" in text
    assert "## Wave 1 priorities" in text
    assert "dispatch automation" in text
    assert "checkpointed reclaim drill" in text
    assert "consistency auto-gate" in text


def test_worker_collaboration_review_records_strengths_gaps_and_verdict():
    text = _read("summaries/worker-collaboration-effectiveness-review.md")

    assert "# Worker collaboration effectiveness review" in text
    assert "## What worked" in text
    assert "## Where it was weak" in text
    assert "## Overall verdict" in text
    assert "codebuddy" in text and "reasonix" in text


def test_phase4_wave1_closure_is_recorded():
    system = _read("state/system.yaml")
    index_text = _read("INDEX.md")
    design_text = _read("_knowledge/design/INDEX.md")
    process_text = _read("_knowledge/process/INDEX.md")

    assert "phase4_worker_collab_status: wave2_completed" in system

    for rel_path in [
        "tasks/done/P4-w1-dispatch-automation.yaml",
        "tasks/done/P4-w1-checkpointed-reclaim-drill.yaml",
        "tasks/done/P4-w1-consistency-auto-gate.yaml",
    ]:
        assert (OMO_ROOT / rel_path).exists(), rel_path

    assert "[phase4-execution-roadmap.md](plans/phase4-execution-roadmap.md)" in index_text
    assert "[worker-collaboration-effectiveness-review.md](summaries/worker-collaboration-effectiveness-review.md)" in index_text
    assert "[p4-wave1-worker-ops-baseline.md](summaries/p4-wave1-worker-ops-baseline.md)" in index_text
    assert "[phase4-execution-roadmap.md](../../plans/phase4-execution-roadmap.md)" in design_text
    assert "[worker-collaboration-effectiveness-review.md](../../summaries/worker-collaboration-effectiveness-review.md)" in process_text
    assert "[p4-wave1-worker-ops-baseline.md](../../summaries/p4-wave1-worker-ops-baseline.md)" in process_text
