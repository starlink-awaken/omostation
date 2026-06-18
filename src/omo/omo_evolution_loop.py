"""
OMO Evolution Loop — Active remediation daemon (Phase 6).

Watches .omo/debt/items/ for new debt records and dispatches 
auto-remediation tasks via MetaOS.
"""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Any

import yaml

_log = logging.getLogger("omo.evolution")

# ── Paths ──────────────────────────────────────────────────────────────────
_WS = os.environ.get("WORKSPACE") or str(Path.home() / "Workspace")
DEBT_DIR = Path(_WS) / ".omo" / "debt" / "items"
PROPOSAL_DIR = Path(_WS) / ".omo" / "state" / "proposals"

from omo.omo_io import write_yaml_atomic  # noqa: E402


class EvolutionLoop:
    """Watches debt records and triggers evolution workflows."""

    def __init__(self, interval_sec: int = 60):
        self.interval = interval_sec
        self._processed_debts: set[str] = set()
        PROPOSAL_DIR.mkdir(parents=True, exist_ok=True)

    def run_once(self) -> int:
        """Scan debt directory and return number of remediation triggered."""
        _log.info("[EvolutionLoop] Scanning: %s", DEBT_DIR)
        if not DEBT_DIR.exists():
            _log.warning("Debt directory not found: %s", DEBT_DIR)
            return 0

        triggered = 0
        all_files = list(DEBT_DIR.glob("*.yaml"))
        _log.info("[EvolutionLoop] Found %d total YAML files.", len(all_files))
        for debt_file in all_files:
            if debt_file.name in self._processed_debts:
                continue

            try:
                debt_data = yaml.safe_load(debt_file.read_text())
                if self._should_remediate(debt_data):
                    self._dispatch_remediation(debt_data)
                    triggered += 1
                    self._processed_debts.add(debt_file.name)
            except Exception as e:
                _log.error("Failed to process debt %s: %s", debt_file.name, e)

        return triggered

    def _should_remediate(self, debt: dict[str, Any]) -> bool:
        """Filter debts that we know how to fix automatically."""
        # For Phase 6, we focus on BUDGET_EXHAUSTED
        debt_id = debt.get("id", "")
        status = debt.get("status", "open")
        
        if status != "open":
            return False
            
        if "BUDGET" in debt_id or "BUDGET" in debt.get("title", "").upper():
            return True
            
        return False

    def _dispatch_remediation(self, debt: dict[str, Any]) -> None:
        """[Phase 9] Generate a MutationProposal for human review."""
        debt_id = debt.get("id", "unknown")
        _log.info("[EvolutionLoop] Generating MutationProposal for: %s", debt_id)
        
        from datetime import UTC, datetime
        now_iso = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        
        # ── 1. Create the Proposal Envelope ──
        proposal_id = f"PROP-{debt_id.replace('DEBT-', '')}"
        proposal_path = PROPOSAL_DIR / f"{proposal_id}.yaml"
        
        # Define automated fix logic (Mapping debt type to suggested action)
        remediation_type = "config_change"
        target_file = ""
        suggestion = "Manual review required."
        
        if "BUDGET" in debt_id.upper():
            remediation_type = "budget_increase"
            suggestion = "Increase RUNTIME_LLM_BUDGET_USD by 20% or downgrade to deepseek-chat."
            
        payload = {
            "id": proposal_id,
            "title": f"Auto-remediation for {debt_id}",
            "type": remediation_type,
            "status": "pending",
            "debt_id": debt_id,
            "created_at": now_iso,
            "target": target_file,
            "suggestion": suggestion,
            "risk": debt.get("severity", "medium"),
            "impact": debt.get("description", "")
        }
        
        # ── 2. Persist to State Plane ──
        try:
            write_yaml_atomic(proposal_path, payload)
            _log.info("[EvolutionLoop] Proposal created: %s", proposal_path)
            print(f"📦  Evolution Loop: Generated MutationProposal {proposal_id} (Awaiting Cockpit Approval)")
        except Exception as e:
            _log.error("[EvolutionLoop] Failed to save proposal: %s", e)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    _log.info("Starting OMO Evolution Loop (Phase 6)...")
    loop = EvolutionLoop(interval_sec=10)
    try:
        while True:
            count = loop.run_once()
            if count > 0:
                _log.info("Triggered %d remediation workflows.", count)
            time.sleep(loop.interval)
    except KeyboardInterrupt:
        _log.info("Evolution Loop stopped.")
