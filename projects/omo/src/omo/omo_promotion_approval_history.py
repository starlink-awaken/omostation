from __future__ import annotations

from datetime import datetime
from pathlib import Path

import yaml


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _parse_iso8601(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _is_promotion_approval_artifact(path: Path) -> bool:
    return "-promotion-approval-" in path.name and path.suffix == ".yaml"


def _proposal_payload(root: Path, proposal_ref: Path) -> dict | None:
    proposal_path = root / proposal_ref
    if not proposal_path.exists():
        return None
    return _load_yaml(proposal_path)


def _proposal_status(root: Path, proposal_ref: Path) -> str:
    proposal = _proposal_payload(root, proposal_ref)
    if proposal is None:
        return "missing"
    return str(proposal.get("status", "missing"))


def _history_entry(root: Path, omo_ref: Path, approval_path: Path) -> dict[str, object]:
    approval = _load_yaml(approval_path)
    required_fields = [
        ("approval_id", approval.get("approval_id")),
        ("task_id", approval.get("task_id")),
        ("requested_at", approval.get("requested_at")),
        ("approval_status", approval.get("approval_status")),
        ("refs.task_ref", approval.get("refs", {}).get("task_ref")),
        ("refs.readiness_ref", approval.get("refs", {}).get("readiness_ref")),
    ]
    for field_name, field_value in required_fields:
        if field_value is None:
            raise ValueError(f"missing required promotion approval field: {field_name}")

    proposal_id = f"{approval['approval_id']}-proposal"
    proposal_ref = (
        omo_ref / "_truth" / "task-center" / "proposals" / f"{proposal_id}.yaml"
    )
    proposal = _proposal_payload(root, proposal_ref)
    return {
        "approval_id": approval["approval_id"],
        "approval_ref": str(omo_ref / "workers" / "runs" / approval_path.name),
        "task_id": approval["task_id"],
        "task_ref": approval["refs"]["task_ref"],
        "requested_at": approval["requested_at"],
        "approval_status": approval["approval_status"],
        "proposal_id": proposal_id,
        "proposal_ref": str(proposal_ref),
        "proposal_status": "missing"
        if proposal is None
        else str(proposal.get("status", "missing")),
        "approver": approval.get("approver"),
        "approved_at": approval.get("approved_at"),
        "applied_at": None if proposal is None else proposal.get("applied_at"),
        "readiness_ref": approval["refs"]["readiness_ref"],
    }


def build_promotion_approval_history(
    root: Path, omo_dir: str | Path = ".omo", now: str = "2026-06-03T00:15:00Z"
) -> dict[str, object]:
    omo_ref = Path(omo_dir)
    runs_dir = root / omo_ref / "workers" / "runs"
    entries = [
        _history_entry(root, omo_ref, path)
        for path in sorted(runs_dir.glob("*-promotion-approval-*.yaml"))
        if _is_promotion_approval_artifact(path)
    ]
    entries.sort(
        key=lambda item: (_parse_iso8601(item["requested_at"]), item["approval_id"]),
        reverse=True,
    )

    latest = entries[0] if entries else None
    prior = entries[1] if len(entries) > 1 else None
    yaml_packet = {
        "generated_at": now,
        "latest_approval_id": latest["approval_id"] if latest else None,
        "latest_approval_ref": latest["approval_ref"] if latest else None,
        "prior_approval_id": prior["approval_id"] if prior else None,
        "prior_approval_ref": prior["approval_ref"] if prior else None,
        "approval_count": len(entries),
        "requested_count": sum(
            1
            for entry in entries
            if entry["approval_status"] == "requested"
            and entry["proposal_status"] == "proposed"
        ),
        "approved_pending_apply_count": sum(
            1
            for entry in entries
            if entry["approval_status"] == "requested"
            and entry["proposal_status"] == "approved"
        ),
        "granted_count": sum(
            1 for entry in entries if entry["approval_status"] == "granted"
        ),
        "approvals": entries,
    }
    markdown_lines = [
        "# Promotion Approval History",
        "",
        f"Generated at: {now}",
        f"Latest approval: {yaml_packet['latest_approval_id'] or 'none'}",
        f"Prior approval: {yaml_packet['prior_approval_id'] or 'none'}",
        f"Approval count: {yaml_packet['approval_count']}",
    ]
    for entry in entries:
        markdown_lines.extend(
            [
                "",
                f"## Approval: {entry['approval_id']}",
                "",
                f"task_id={entry['task_id']}",
                f"approval_status={entry['approval_status']}",
                f"proposal_status={entry['proposal_status']}",
                f"task_ref={entry['task_ref']}",
            ]
        )
    return {"yaml": yaml_packet, "markdown": "\n".join(markdown_lines) + "\n"}
