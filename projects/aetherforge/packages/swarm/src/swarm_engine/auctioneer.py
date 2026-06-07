"""Market-style task auction for D_Execution worker allocation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class MarketConfig:
    """Configuration for the task auction market."""

    min_bid_threshold: float = 0.0
    auction_timeout: float = 5.0
    strategy: str = "highest_bid"
    require_explicit_bid: bool = True
    max_bidders: int = 10
    metadata: dict[str, Any] = field(default_factory=dict)


class TaskAuctioneer:
    """Orchestrates task auctions: collects bids and selects winners.

    Bids are plain ``dict[str, Any]`` as produced by
    :meth:`TaskBidder.create_bid`, expected to contain ``"bid_price"``,
    ``"node_id"``, ``"task_id"``, and ``"capability_match"`` keys.
    """

    def __init__(self, config: MarketConfig | None = None) -> None:
        self.config = config or MarketConfig()

    def conduct_auction(
        self,
        task_id: str,
        bids: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        """Run an auction and return the winning bid, or ``None`` if no
        valid bid meets the threshold."""
        valid = [b for b in bids if b.get("bid_price", 0) >= self.config.min_bid_threshold]
        if not valid:
            return None

        strategy_fn = getattr(self, f"_strategy_{self.config.strategy}", self._strategy_highest_bid)
        return strategy_fn(valid)

    def _strategy_highest_bid(self, bids: list[dict[str, Any]]) -> dict[str, Any]:
        return max(bids, key=lambda b: b.get("bid_price", 0))

    def _strategy_lowest_load(self, bids: list[dict[str, Any]]) -> dict[str, Any]:
        return min(bids, key=lambda b: b.get("load_factor", 0))

    def _strategy_round_robin(self, bids: list[dict[str, Any]]) -> dict[str, Any]:
        bids_sorted = sorted(bids, key=lambda b: b.get("node_id", ""))
        return bids_sorted[0]
