"""Anti-corruption adapter for projects/omo (L2)."""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import omo.omo_ingress as omo_ingress  # type: ignore[import-not-found]
from omo.omo_cockpit_bridge import (  # type: ignore[import-not-found]
    append_hitl_override,
    approve_hitl_proposal_async,
    list_hitl_proposals,
    record_hitl_proposal,
    reject_hitl_proposal,
)
from omo.omo_io import write_text_atomic, write_yaml_atomic  # type: ignore[import-not-found]
from omo.omo_shared import load_yaml  # type: ignore[import-not-found]


def _bridge_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


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


from omo.omo_dashboard import _load_json as load_json  # type: ignore[import-not-found]
from omo.omo_debt_registry import load_debt_ledger  # type: ignore[import-not-found]
from omo.omo_ingress import complete_task  # type: ignore[import-not-found]

__all__ = [
    "append_hitl_override",
    "archive_scenario_receipt",
    "approve_hitl_proposal_async",
    "complete_task",
    "list_hitl_proposals",
    "load_debt_ledger",
    "load_json",
    "omo_ingress",
    "record_hitl_proposal",
    "reject_hitl_proposal",
    "update_provider_plane_settings",
]
