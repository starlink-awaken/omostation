from __future__ import annotations

from datetime import datetime
from pathlib import Path

import yaml


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _parse_iso8601(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _is_promotion_envelope(path: Path) -> bool:
    return "-promotion-" in path.name and "-promotion-approval-" not in path.name


def _history_entry(omo_ref: Path, envelope_path: Path) -> dict[str, object]:
    envelope = _load_yaml(envelope_path)
    required_fields = [
        ("promotion_id", envelope.get("promotion_id")),
        ("task_id", envelope.get("task_id")),
        ("promoted_at", envelope.get("promoted_at")),
        ("promoted_by", envelope.get("promoted_by")),
        ("task_ref_before", envelope.get("task_ref_before")),
        ("task_ref_after", envelope.get("task_ref_after")),
        ("approval.required", envelope.get("approval", {}).get("required")),
        ("phase_gate.target_phase", envelope.get("phase_gate", {}).get("target_phase")),
    ]
    for field_name, field_value in required_fields:
        if field_value is None:
            raise ValueError(f"missing required promotion field: {field_name}")

    return {
        "promotion_id": envelope["promotion_id"],
        "promotion_ref": str(omo_ref / "workers" / "runs" / envelope_path.name),
        "task_id": envelope["task_id"],
        "promoted_at": envelope["promoted_at"],
        "promoted_by": envelope["promoted_by"],
        "task_ref_before": envelope["task_ref_before"],
        "task_ref_after": envelope["task_ref_after"],
        "approval_required": envelope["approval"]["required"],
        "approval_ref": envelope.get("approval", {}).get("approval_ref"),
        "target_phase": envelope["phase_gate"]["target_phase"],
    }


def build_promotion_history(
    root: Path, omo_dir: str | Path = ".omo", now: str = "2026-06-03T00:00:00Z"
) -> dict[str, object]:
    omo_ref = Path(omo_dir)
    runs_dir = root / omo_ref / "workers" / "runs"
    entries = [
        _history_entry(omo_ref, path)
        for path in sorted(runs_dir.glob("*-promotion-*.yaml"))
        if _is_promotion_envelope(path)
    ]
    entries.sort(key=lambda item: _parse_iso8601(item["promoted_at"]), reverse=True)

    latest = entries[0] if entries else None
    prior = entries[1] if len(entries) > 1 else None
    yaml_packet = {
        "generated_at": now,
        "latest_promotion_id": latest["promotion_id"] if latest else None,
        "latest_promotion_ref": latest["promotion_ref"] if latest else None,
        "prior_promotion_id": prior["promotion_id"] if prior else None,
        "prior_promotion_ref": prior["promotion_ref"] if prior else None,
        "promotion_count": len(entries),
        "promotions": entries,
    }
    markdown_lines = [
        "# Task Promotion History",
        "",
        f"Generated at: {now}",
        f"Latest promotion: {yaml_packet['latest_promotion_id'] or 'none'}",
        f"Prior promotion: {yaml_packet['prior_promotion_id'] or 'none'}",
    ]
    for entry in entries:
        markdown_lines.extend(
            [
                "",
                f"## Promotion: {entry['promotion_id']}",
                "",
                f"task_id={entry['task_id']}",
                f"promotion_ref={entry['promotion_ref']}",
                f"task_ref_after={entry['task_ref_after']}",
                f"approval_required={'yes' if entry['approval_required'] else 'no'}",
                f"target_phase={entry['target_phase']}",
            ]
        )

    return {"yaml": yaml_packet, "markdown": "\n".join(markdown_lines) + "\n"}
