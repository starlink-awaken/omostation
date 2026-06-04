from __future__ import annotations

from pathlib import Path


APPROVAL_SCOPE_EXECUTE_REVALIDATE = "execute_revalidate"
VALID_APPROVAL_SCOPES = {
    APPROVAL_SCOPE_EXECUTE_REVALIDATE,
    "promote_lifecycle",
    "escalate",
}


def find_dispatch_entry(dispatch_packet: dict[str, object], item_id: str) -> dict[str, object] | None:
    for owner_packet in dispatch_packet.get("owners", []):
        for entry in owner_packet.get("entries", []):
            if entry.get("id") == item_id:
                return dict(entry)
    return None


def dispatch_entry_requires_approval(entry: dict[str, object] | None) -> bool:
    if entry is None:
        return False
    return entry.get("primary_lane") == "revalidate_now" and entry.get("gate_level") == "gate"


def approval_current_path(omo_dir: Path, item_id: str) -> Path:
    return omo_dir / "debt" / "approvals" / item_id / "current.yaml"


def approval_paths(omo_dir: Path, item_id: str, approved_at: str) -> tuple[Path, Path]:
    slug = approved_at.replace(":", "-")
    item_dir = approval_current_path(omo_dir, item_id).parent
    return item_dir / "current.yaml", item_dir / "records" / f"{slug}.yaml"


def build_approval_record(
    *,
    item_id: str,
    approved_by: str,
    approved_at: str,
    dispatch_run_ref: str,
    approval_scope: str,
) -> dict[str, str]:
    if approval_scope not in VALID_APPROVAL_SCOPES:
        raise ValueError(f"invalid approval scope: {approval_scope}")
    return {
        "item_id": item_id,
        "approved_by": approved_by,
        "approved_at": approved_at,
        "dispatch_run_ref": dispatch_run_ref,
        "approval_scope": approval_scope,
    }
