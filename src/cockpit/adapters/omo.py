"""Anti-corruption adapter for projects/omo (L2).

Re-exports the OMO symbols used by cockpit CLI/Web surfaces.
"""

import omo.omo_ingress as omo_ingress
from omo.omo_cockpit_bridge import (
    append_hitl_override,
    approve_hitl_proposal_async,
    archive_scenario_receipt,
    list_hitl_proposals,
    reject_hitl_proposal,
    update_provider_plane_settings,
)
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
