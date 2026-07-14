"""Anti-corruption adapter for projects/omo (L2).

Re-exports the OMO symbols used by cockpit CLI/Web surfaces.  The bridge was
removed from the current OMO checkout during module cleanup, so the small
compatibility surface below remains owned by this adapter until all callers
move to the newer governance APIs.
"""

import inspect
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import omo.omo_ingress as omo_ingress

try:
    from omo.omo_cockpit_bridge import (
        append_hitl_override,
        approve_hitl_proposal_async,
        archive_scenario_receipt,
        list_hitl_proposals,
        reject_hitl_proposal,
        update_provider_plane_settings,
    )
except ModuleNotFoundError as exc:
    if exc.name != "omo.omo_cockpit_bridge":
        raise

    from omo.omo_io import AppendOnlyLog, fcntl_lock, write_text_atomic, write_yaml_atomic
    from omo.omo_shared import load_yaml

    def _bridge_now() -> str:
        return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    def _proposal_dir(omo_dir: Path) -> Path:
        return omo_dir / "state" / "proposals"

    def list_hitl_proposals(omo_dir: Path) -> list[dict[str, Any]]:
        proposal_dir = _proposal_dir(omo_dir)
        proposals = []
        for path in proposal_dir.glob("*.yaml") if proposal_dir.exists() else []:
            data = load_yaml(path)
            if isinstance(data, dict):
                proposals.append(data)
        return sorted(proposals, key=lambda item: item.get("created_at", ""), reverse=True)

    def append_hitl_override(omo_dir: Path, stream_name: str, record: dict[str, Any]) -> str:
        path = omo_dir / "state" / stream_name
        AppendOnlyLog(path, lock=fcntl_lock(path.with_suffix(path.suffix + ".lock"))).append(record, sort_keys=False)
        return str(path)

    async def approve_hitl_proposal_async(
        omo_dir: Path, proposal_id: str, *, execute_mutation
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
            return False, f"Proposal {proposal_id} is already being processed or locked."
        try:
            proposal = load_yaml(processing_path)
            result = execute_mutation(proposal)
            success = await result if inspect.isawaitable(result) else result
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
        path = _proposal_dir(omo_dir) / f"{proposal_id}.yaml"
        if not path.exists():
            return False
        proposal = load_yaml(path) or {}
        proposal["status"] = "rejected"
        proposal["rejected_at"] = _bridge_now()
        write_yaml_atomic(path, proposal)
        return True

    def archive_scenario_receipt(omo_dir: Path, result: dict[str, Any]) -> str:
        scenario = str(result.get("scenario", "unknown"))
        out_dir = omo_dir / "_delivery" / "scenarios" / scenario
        out_dir.mkdir(parents=True, exist_ok=True)
        ts = _bridge_now().replace(":", "").replace("-", "")
        hint = str(result.get("query", scenario)).strip().lower().replace("/", "-").replace(" ", "-")
        hint = "".join(ch for ch in hint if ch.isalnum() or ch in {"-", "_"})[:48] or scenario
        out_path = out_dir / f"{ts}-{hint}-{uuid4().hex[:8]}.json"
        write_text_atomic(out_path, json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        return str(out_path)

    def update_provider_plane_settings(
        omo_dir: Path, circuit_broken: bool | None = None, daily_budget: float | None = None
    ) -> bool:
        plane_path = omo_dir / "state" / "provider-plane.yaml"
        if not plane_path.exists():
            return False
        try:
            data = load_yaml(plane_path) or {}
            if circuit_broken is not None:
                data["circuit_broken"] = circuit_broken
            if daily_budget is not None:
                data["daily_budget"] = daily_budget
            write_yaml_atomic(plane_path, data)
            return True
        except (OSError, TypeError, ValueError):
            return False


from omo.omo_dashboard import _load_json as load_json
from omo.omo_debt_registry import load_debt_ledger
from omo.omo_ingress import complete_task

__all__ = [
    "append_hitl_override",
    "archive_scenario_receipt",
    "approve_hitl_proposal_async",
    "complete_task",
    "list_hitl_proposals",
    "load_debt_ledger",
    "load_json",
    "omo_ingress",
    "reject_hitl_proposal",
    "update_provider_plane_settings",
]
