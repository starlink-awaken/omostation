from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import yaml

from omo.omo_io import AppendOnlyLog, fcntl_lock, write_text_atomic


def _utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _proposal_dir(omo_dir: Path) -> Path:
    return omo_dir / "state" / "proposals"


def _jsonl_path(omo_dir: Path, name: str) -> Path:
    return omo_dir / "state" / name


def _scenario_root(omo_dir: Path) -> Path:
    return omo_dir / "_delivery" / "scenarios"


def list_hitl_proposals(omo_dir: Path) -> list[dict[str, Any]]:
    proposal_dir = _proposal_dir(omo_dir)
    if not proposal_dir.exists():
        return []

    proposals: list[dict[str, Any]] = []
    for path in proposal_dir.glob("*.yaml"):
        data = _load_yaml(path)
        if isinstance(data, dict):
            proposals.append(data)
    proposals.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return proposals


def append_hitl_override(omo_dir: Path, stream_name: str, record: dict[str, Any]) -> str:
    path = _jsonl_path(omo_dir, stream_name)
    lock = path.with_suffix(path.suffix + ".lock")
    AppendOnlyLog(path, lock=fcntl_lock(lock)).append(record, sort_keys=False)
    return str(path)


def approve_hitl_proposal(
    omo_dir: Path,
    proposal_id: str,
    *,
    execute_mutation,
) -> tuple[bool, str | None]:
    proposal_dir = _proposal_dir(omo_dir)
    proposal_path = proposal_dir / f"{proposal_id}.yaml"
    processing_path = proposal_dir / f"{proposal_id}.processing"

    if not proposal_path.exists() and not processing_path.exists():
        return False, f"Proposal {proposal_id} not found"

    try:
        if proposal_path.exists():
            proposal_path.rename(processing_path)
    except OSError:
        return False, f"Proposal {proposal_id} is already being processed."

    try:
        proposal = _load_yaml(processing_path)
        success = execute_mutation(proposal)
        if not success:
            processing_path.rename(proposal_path)
            return False, f"No execution logic for type {proposal.get('type')}"
        processing_path.unlink()
        return True, None
    except Exception as exc:
        if processing_path.exists():
            processing_path.rename(proposal_path)
        return False, str(exc)


async def approve_hitl_proposal_async(
    omo_dir: Path,
    proposal_id: str,
    *,
    execute_mutation,
) -> tuple[bool, str | None]:
    """[Phase 15] Asynchronous Two-Phase Approval."""
    proposal_dir = _proposal_dir(omo_dir)
    proposal_path = proposal_dir / f"{proposal_id}.yaml"
    processing_path = proposal_dir / f"{proposal_id}.processing"

    if not proposal_path.exists() and not processing_path.exists():
        return False, f"Proposal {proposal_id} not found"

    # 1. Lock (Rename)
    try:
        if proposal_path.exists():
            proposal_path.rename(processing_path)
    except OSError:
        return False, f"Proposal {proposal_id} is already being processed or locked."

    # 2. Execute & Commit/Rollback
    try:
        proposal = _load_yaml(processing_path)
        
        import inspect
        if inspect.iscoroutinefunction(execute_mutation):
            success = await execute_mutation(proposal)
        else:
            success = execute_mutation(proposal)
            
        if not success:
            processing_path.rename(proposal_path)
            return False, f"No execution logic for type {proposal.get('type')}"
            
        processing_path.unlink()
        return True, None
    except Exception as exc:
        if processing_path.exists():
            processing_path.rename(proposal_path)
        return False, str(exc)


def reject_hitl_proposal(omo_dir: Path, proposal_id: str) -> bool:
    proposal_path = _proposal_dir(omo_dir) / f"{proposal_id}.yaml"
    if proposal_path.exists():
        proposal_path.unlink()
        return True
    return False


def archive_scenario_receipt(omo_dir: Path, result: dict[str, Any]) -> str:
    scenario = str(result.get("scenario", "unknown"))
    out_dir = _scenario_root(omo_dir) / scenario
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = _utc_now().replace(":", "").replace("-", "")
    query_hint = str(result.get("query", scenario)).strip().lower().replace("/", "-").replace(" ", "-")
    if not query_hint:
        query_hint = scenario
    query_hint = "".join(ch for ch in query_hint if ch.isalnum() or ch in {"-", "_"})[:48] or scenario
    out_path = out_dir / f"{ts}-{query_hint}-{uuid4().hex[:8]}.json"
    write_text_atomic(out_path, json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    return str(out_path)
