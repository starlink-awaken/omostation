from __future__ import annotations

from pathlib import Path

from .omo_io import write_text_atomic


def write_metrics_trend(workspace_root: Path, content: str) -> Path:
    output_file = workspace_root / ".omo" / "_delivery" / "audit-rollout" / "metrics-trend.txt"
    write_text_atomic(output_file, content)
    return output_file
