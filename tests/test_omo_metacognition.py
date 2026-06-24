from __future__ import annotations

from pathlib import Path

from omo.omo_metacognition import _phase12_evidence


def test_phase12_evidence_reads_compatibility_alias_inputs(tmp_path: Path) -> None:
    trace_path = (
        tmp_path / ".omo" / "evidence" / "phase12" / "research-pipeline-trace.yaml"
    )
    trace_path.parent.mkdir(parents=True, exist_ok=True)
    trace_path.write_text(
        "status: ok\nsteps:\n  - collect\nmissing_capabilities: []\n",
        encoding="utf-8",
    )
    dry_run_path = tmp_path / ".omo" / "evidence" / "phase12" / "package-dry-run.yaml"
    dry_run_path.write_text(
        "mutations_applied: 0\npackages_checked: 3\n",
        encoding="utf-8",
    )

    evidence = _phase12_evidence(tmp_path)

    assert evidence["trace_status"] == "ok"
    assert evidence["trace_steps"] == 1
    assert evidence["package_mutations"] == 0
    assert evidence["packages_checked"] == 3
