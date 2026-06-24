from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .omo_io import write_text_atomic


def write_phase_gate_audit(
    workspace_root: Path, payload: dict[str, Any], today: str
) -> tuple[Path, Path]:
    out_dir = workspace_root / ".omo" / "_delivery" / "phase-gate"
    json_path = out_dir / f"{today}.json"
    write_text_atomic(
        json_path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    )
    md_path = out_dir / f"{today}.md"
    lines = [
        f"# Phase Gate Matrix — {today}",
        "",
        f"Generated: {payload['generated_at']}",
        "",
    ]
    lines.append("## Summary")
    lines.append(f"- phases_total: {payload['summary']['phases_total']}")
    lines.append(f"- phases_passed: **{payload['summary']['phases_passed']}**")
    lines.append(f"- phases_open: {payload['summary']['phases_open']}")
    lines.append("")
    lines.append("| Phase | Gate | Status | Sub-gates |")
    lines.append("|-------|------|--------|-----------|")
    for row in payload["rows"]:
        lines.append(
            f"| {row['phase']} | {row['gate']} | {row['gate_status']} | "
            f"{row['sub_gate_passed']}/{row['sub_gate_count']} passed, {row['sub_gate_open']} open |"
        )
    write_text_atomic(md_path, "\n".join(lines) + "\n")
    return json_path, md_path
