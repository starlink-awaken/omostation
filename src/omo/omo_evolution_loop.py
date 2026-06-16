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


class EvolutionLoop:
    """Watches debt records and triggers evolution workflows."""

    def __init__(self, interval_sec: int = 60):
        self.interval = interval_sec
        self._processed_debts: set[str] = set()

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
        """Trigger a MetaOS workflow to propose a fix."""
        debt_id = debt.get("id", "unknown")
        _log.info("[EvolutionLoop] Triggering remediation for: %s", debt_id)
        
        # In Phase 6, we simulate the dispatch or call a MetaOS CLI
        # TODO: integrate with actual metaos.py or a2a_send
        
        print(f"🛠️  Evolution Loop: Dispatched remediation for debt {debt_id}")
        print(f"   Reason: {debt.get('description', 'No description')}")
        print(f"   Target: Auto-downgrade model or increase budget proposal.")


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
