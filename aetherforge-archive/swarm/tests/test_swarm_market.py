"""Swarm market mechanics: auctioneer, bidder, arbitrator.

Task F68B791B: AUDIT 1.x thin-test remediation for swarm_engine core.
Covers:
- TaskAuctioneer: highest-bid selection + threshold filtering
- TaskBidder: capability matching, loss-streak price decay
- ConflictArbitrator: priority-first policy + empty-claim edge case
"""

from __future__ import annotations


class TestTaskAuctioneer:
    def test_highest_bid_wins(self):
        from swarm_engine.auctioneer import MarketConfig, TaskAuctioneer

        auctioneer = TaskAuctioneer(MarketConfig(strategy="highest_bid"))
        bids = [
            {"node_id": "n1", "bid_price": 5.0, "task_id": "t1"},
            {"node_id": "n2", "bid_price": 9.5, "task_id": "t1"},
            {"node_id": "n3", "bid_price": 7.2, "task_id": "t1"},
        ]
        winner = auctioneer.conduct_auction("t1", bids)
        assert winner is not None
        assert winner["node_id"] == "n2"
        assert winner["bid_price"] == 9.5

    def test_min_bid_threshold_filters_low_bids(self):
        from swarm_engine.auctioneer import MarketConfig, TaskAuctioneer

        auctioneer = TaskAuctioneer(MarketConfig(strategy="highest_bid", min_bid_threshold=6.0))
        bids = [
            {"node_id": "n1", "bid_price": 5.0, "task_id": "t1"},  # filtered
            {"node_id": "n2", "bid_price": 6.5, "task_id": "t1"},
            {"node_id": "n3", "bid_price": 8.0, "task_id": "t1"},
        ]
        winner = auctioneer.conduct_auction("t1", bids)
        assert winner["node_id"] == "n3"  # type: ignore[reportOptionalSubscript]
        assert winner["bid_price"] == 8.0  # type: ignore[reportOptionalSubscript]

    def test_empty_or_all_filtered_returns_none(self):
        from swarm_engine.auctioneer import MarketConfig, TaskAuctioneer

        auctioneer = TaskAuctioneer(MarketConfig(min_bid_threshold=10.0))
        assert auctioneer.conduct_auction("t1", []) is None
        assert auctioneer.conduct_auction("t1", [{"node_id": "n1", "bid_price": 1.0, "task_id": "t1"}]) is None


class TestTaskBidder:
    def test_capability_match_ratio(self):
        from swarm_engine.bidder import TaskBidder

        bidder = TaskBidder("n1")
        bidder.add_capability("python")
        bidder.add_capability("async")
        bidder.add_capability("sql")
        # Required: python + sql + rust → match 2/3 ≈ 0.667
        match = bidder.evaluate_capability_match({"capabilities": ["python", "sql", "rust"]})
        assert abs(match - (2 / 3)) < 0.001

    def test_no_required_capabilities_returns_full_match(self):
        from swarm_engine.bidder import TaskBidder

        bidder = TaskBidder("n1")
        assert bidder.evaluate_capability_match({"capabilities": []}) == 1.0
        assert bidder.evaluate_capability_match({}) == 1.0

    def test_loss_streak_lowers_price_multiplier(self):
        from swarm_engine.bidder import TaskBidder

        bidder = TaskBidder("n1")
        rfp = {"eu_budget": 10.0, "task_id": "t1"}
        baseline = bidder.calculate_bid_price(rfp, load=0.5)
        # Three consecutive losses should trigger decay (≥ 3 boundary).
        bidder.record_loss()
        bidder.record_loss()
        bidder.record_loss()
        decayed = bidder.calculate_bid_price(rfp, load=0.5)
        assert decayed < baseline
        assert decayed >= baseline * 0.5  # floor at 0.5 of base

    def test_record_win_resets_loss_streak(self):
        from swarm_engine.bidder import TaskBidder

        bidder = TaskBidder("n1")
        rfp = {"eu_budget": 10.0, "task_id": "t1"}
        bidder.record_loss()
        bidder.record_loss()
        bidder.record_loss()
        bidder.record_win()  # reset
        # After reset, multiplier back to 1.0 → price equals first call.
        price_after = bidder.calculate_bid_price(rfp, load=0.5)
        first = TaskBidder("n1").calculate_bid_price(rfp, load=0.5)
        assert price_after == first


class TestConflictArbitrator:
    def test_priority_first_policy_picks_highest(self):
        from swarm_engine.arbitrator import ConflictArbitrator

        arbitrator = ConflictArbitrator(policy="priority_first")
        claims = [
            {"worker_id": "w1", "task_id": "t1", "priority": 5},
            {"worker_id": "w2", "task_id": "t1", "priority": 9},
            {"worker_id": "w3", "task_id": "t1", "priority": 7},
        ]
        winner = arbitrator.arbitrate(claims, "gpu-0")
        assert winner is not None
        assert winner["worker_id"] == "w2"

    def test_empty_claims_returns_none(self):
        from swarm_engine.arbitrator import ConflictArbitrator

        arbitrator = ConflictArbitrator(policy="priority_first")
        assert arbitrator.arbitrate([], "gpu-0") is None

    def test_invalid_policy_raises_value_error(self):
        from swarm_engine.arbitrator import ConflictArbitrator

        try:
            ConflictArbitrator(policy="unknown_policy")
        except ValueError:
            return
        raise AssertionError("expected ValueError for unknown policy")
