from __future__ import annotations

import json
from pathlib import Path

from omo.omo_demo_artifacts import (
    write_budget_audit_llm_sample,
    write_budget_audit_rollout_summary,
    write_budget_reject_summary,
)


def test_demo_artifact_helpers_write_outputs(tmp_path: Path) -> None:
    llm_path = write_budget_audit_llm_sample(tmp_path, {"provider": "anthropic"})
    summary_path = write_budget_audit_rollout_summary(
        tmp_path,
        tmp_path / "sample.json",
        0,
        "ok",
        "",
    )
    reject_path = write_budget_reject_summary(
        tmp_path,
        tmp_path / "debt.yaml",
        "budget blocked",
    )

    assert json.loads(llm_path.read_text(encoding="utf-8"))["provider"] == "anthropic"
    assert "returncode: 0" in summary_path.read_text(encoding="utf-8")
    assert "budget blocked" in reject_path.read_text(encoding="utf-8")
