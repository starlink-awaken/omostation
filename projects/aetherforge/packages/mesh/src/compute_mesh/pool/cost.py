"""CostTracker — records and reports compute resource usage costs.

Integrates with:
  - eCOS X3 value stack (record_llm_cost → JSONL)
  - Mesh topology node cost_per_1k_tokens
  - Quota rates cache (~/.runtime/cache/quota_rates.json)
"""

from __future__ import annotations

import json
import logging
import os
import time
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ..topology import NodeRegistry
from .cost_db import CostDB

_log = logging.getLogger(__name__)

# Default cost log path (same convention as llm-gateway's record_llm_cost)
COST_LOG = Path(os.environ.get("RUNTIME_HOME", str(Path.home() / "runtime"))) / "data" / "mesh_cost.jsonl"

# Path for cached quota rates from models list --json
QUOTA_RATES_CACHE = Path.home() / ".runtime" / "cache" / "quota_rates.json"


class CostTracker:
    """Records and reports compute usage costs across the mesh.

    Usage::

        tracker = CostTracker(registry)
        tracker.record("ollama-local", prompt_tokens=100, completion_tokens=50)
        report = tracker.get_report()
    """

    def __init__(
        self,
        registry: NodeRegistry,
        cost_log_path: str | Path = COST_LOG,
    ) -> None:
        self._registry = registry
        self._cost_log = Path(cost_log_path)
        self._session_costs: dict[str, float] = defaultdict(float)
        self._session_requests: dict[str, int] = defaultdict(int)
        self._db = CostDB()

    # ── Recording ────────────────────────────────────────────────────────────

    def record(
        self,
        node_id: str,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        model: str = "",
    ) -> None:
        """Record a compute usage event for a node.

        Writes a JSONL entry to the cost log (non-blocking) and updates
        in-memory session counters.
        """
        node = self._registry.get(node_id)
        rates = node.cost_per_1k_tokens if node else {"input": 0.0, "output": 0.0}

        cost_input = (prompt_tokens / 1000) * rates.get("input", 0)
        cost_output = (completion_tokens / 1000) * rates.get("output", 0)
        total_cost = cost_input + cost_output

        self._session_costs[node_id] += total_cost
        self._session_requests[node_id] += 1

        # Dual write: SQLite + JSONL
        self._db.record(
            node_id=node_id,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_cost=total_cost,
            cost_input=cost_input,
            cost_output=cost_output,
        )

        # Legacy JSONL (for backwards compat)
        entry = {
            "ts": datetime.now(UTC).isoformat(),
            "node_id": node_id,
            "model": model,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "cost_input": round(cost_input, 6),
            "cost_output": round(cost_output, 6),
            "total_cost": round(total_cost, 6),
        }
        self._write_log(entry)

    def record_llm(
        self,
        node_id: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
    ) -> None:
        """Convenience wrapper matching gateway's ``record_llm_cost`` signature."""
        self.record(
            node_id=node_id,
            prompt_tokens=input_tokens,
            completion_tokens=output_tokens,
            model=model,
        )

    def _write_log(self, entry: dict[str, Any]) -> None:
        try:
            self._cost_log.parent.mkdir(parents=True, exist_ok=True)
            line = (json.dumps(entry, ensure_ascii=False) + "\n").encode("utf-8")
            fd = os.open(str(self._cost_log), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
            try:
                os.write(fd, line)
            finally:
                os.close(fd)
        except Exception:
            _log.exception("Failed to write cost log entry")

    # ── Reporting ────────────────────────────────────────────────────────────

    def get_report(self) -> dict[str, Any]:
        """Return a cost report (SQLite aggregated + session data)."""
        # Session-level data
        session_total = sum(self._session_costs.values())
        session_requests = sum(self._session_requests.values())

        node_details = []
        for node_id in self._session_costs:
            node_details.append(
                {
                    "node_id": node_id,
                    "requests": self._session_requests[node_id],
                    "total_cost": round(self._session_costs[node_id], 6),
                }
            )

        # SQLite persistent data
        db_report = self._db.get_report()

        return {
            "session": {
                "total_cost": round(session_total, 6),
                "total_requests": session_requests,
                "nodes": node_details,
            },
            "all_time": {
                "total_cost": db_report["total_cost"],
                "total_requests": db_report["total_requests"],
                "total_prompt_tokens": db_report["total_prompt_tokens"],
                "total_completion_tokens": db_report["total_completion_tokens"],
                "nodes": len(db_report["per_node"]),
            },
            "db_path": str(self._db._db_path),
            "jsonl_path": str(self._db._jsonl_path),
        }

    def get_db(self) -> CostDB:
        """Access the underlying SQLite cost database directly."""
        return self._db

    def reset_session(self) -> None:
        """Reset in-memory session counters."""
        self._session_costs.clear()
        self._session_requests.clear()

    # ── Quota rates ──────────────────────────────────────────────────────────

    def load_quota_rates(self) -> int:
        """Load real prices from ``quota_rates.json`` cache into node cost fields.

        Returns the number of nodes updated.
        """
        if not QUOTA_RATES_CACHE.exists():
            return 0

        try:
            with open(QUOTA_RATES_CACHE) as f:
                data = json.load(f)
        except (json.JSONDecodeError, Exception):
            return 0

        rates = data.get("rates", {})
        updated = 0
        for node in self._registry.get_all():
            short_name = node.node_id.split("/")[-1]
            if short_name in rates:
                r = rates[short_name]
                if r.get("input") is not None:
                    node.cost_per_1k_tokens["input"] = r["input"]
                    node.cost_per_1k_tokens["output"] = r.get("output", r["input"])
                    updated += 1
        return updated

    # ── History ──────────────────────────────────────────────────────────────

    def read_log(self, tail: int = 100) -> list[dict[str, Any]]:
        """Read the last *tail* entries from the cost log."""
        if not self._cost_log.exists():
            return []
        try:
            with open(self._cost_log) as f:
                lines = f.readlines()
            entries = []
            for line in lines[-tail:]:
                line = line.strip()
                if line:
                    entries.append(json.loads(line))
            return entries
        except Exception:
            return []
