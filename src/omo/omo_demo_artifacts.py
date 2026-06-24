from __future__ import annotations

import json
from pathlib import Path

from .omo_io import write_text_atomic


def write_budget_audit_llm_sample(workspace_root: Path, audit_record: dict) -> Path:
    out_path = (
        workspace_root
        / ".omo"
        / "tasks"
        / "registry"
        / "done"
        / "OPC-P4-E4"
        / "llm-audit-sample.json"
    )
    write_text_atomic(
        out_path, json.dumps(audit_record, ensure_ascii=False, indent=2) + "\n"
    )
    return out_path


def write_budget_audit_rollout_summary(
    workspace_root: Path, rollout_out: Path, returncode: int, stdout: str, stderr: str
) -> Path:
    out_path = (
        workspace_root
        / ".omo"
        / "tasks"
        / "registry"
        / "done"
        / "OPC-P4-E4"
        / "audit-rollout-summary.md"
    )
    write_text_atomic(
        out_path,
        "\n".join(
            [
                "# OPC P4 E4 rollout summary",
                "",
                f"- returncode: {returncode}",
                f"- output: `{rollout_out}`",
                "",
                "```text",
                stdout.strip(),
                stderr.strip(),
                "```",
                "",
            ]
        ),
    )
    return out_path


def write_budget_reject_summary(
    workspace_root: Path, debt_path: Path, error: str
) -> Path:
    out_path = (
        workspace_root
        / ".omo"
        / "tasks"
        / "registry"
        / "done"
        / "OPC-P4-E3"
        / "budget-reject-summary.md"
    )
    write_text_atomic(
        out_path,
        "\n".join(
            [
                "# OPC P4 E3 budget reject summary",
                "",
                f"- debt: `{debt_path}`",
                f"- error: `{error}`",
                "",
            ]
        ),
    )
    return out_path
