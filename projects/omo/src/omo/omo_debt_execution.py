from __future__ import annotations

from pathlib import Path


def run_slug_from_ref(dispatch_run_ref: str) -> str:
    run_path = Path(dispatch_run_ref)
    if run_path.suffix != ".yaml":
        raise ValueError(f"dispatch run ref must point to a .yaml artifact: {dispatch_run_ref}")
    return run_path.stem


def execution_record_path(omo_dir: Path, dispatch_run_ref: str, item_id: str) -> Path:
    return omo_dir / "debt" / "dispatch" / "executions" / run_slug_from_ref(dispatch_run_ref) / f"{item_id}.yaml"


def build_execution_record(item_id: str, dispatch_run_ref: str, reviewed_at: str) -> dict[str, str]:
    return {
        "item_id": item_id,
        "dispatch_run_ref": dispatch_run_ref,
        "action": "revalidate",
        "reviewed_at": reviewed_at,
    }
