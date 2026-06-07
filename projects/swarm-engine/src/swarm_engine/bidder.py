from __future__ import annotations

import logging
from typing import Any

_log = logging.getLogger(__name__)


class TaskBidder:
    """Evaluates RFPs and submits competitive bids for swarm tasks.

    Based on nucleus D_Execution bidder organ.
    Tracks consecutive losses to adjust pricing.
    """

    def __init__(self, node_id: str = "stub-node") -> None:
        self.node_id = node_id
        self._capabilities: set[str] = set()
        self._consecutive_losses = 0
        self._price_multiplier = 1.0

    def add_capability(self, capability: str) -> None:
        self._capabilities.add(capability)

    def evaluate_capability_match(self, rfp: dict[str, Any]) -> float:
        required = set(rfp.get("capabilities", []))
        if not required:
            return 1.0
        matches = required.intersection(self._capabilities)
        return len(matches) / len(required)

    def calculate_bid_price(self, rfp: dict[str, Any], load: float = 0.5) -> float:
        budget = rfp.get("eu_budget", 10.0)
        base_price = budget * 0.8
        load_factor = (load - 0.5) * 0.4
        final_price = base_price * (1.0 + load_factor) * self._price_multiplier
        return round(final_price, 2)

    def record_win(self) -> None:
        self._consecutive_losses = 0
        self._price_multiplier = 1.0

    def record_loss(self) -> None:
        self._consecutive_losses += 1
        if self._consecutive_losses >= 3:
            self._price_multiplier = max(0.5, self._price_multiplier * 0.95)

    def create_bid(self, rfp: dict[str, Any], load: float = 0.5) -> dict[str, Any]:
        match = self.evaluate_capability_match(rfp)
        if match < 0.1:
            return {}
        price = self.calculate_bid_price(rfp, load)
        return {
            "node_id": self.node_id,
            "task_id": rfp.get("task_id"),
            "bid_price": price,
            "capability_match": match,
            "reputation": 0.0,
            "timestamp": 0.0,
        }

    def create_batch_bid(self, batch_rfp: dict[str, Any], load: float = 0.5) -> list[dict[str, Any]]:
        tasks = batch_rfp.get("tasks", [])
        return [b for b in [self.create_bid(t, load) for t in tasks] if b]
