"""Tests for autonomy ladder (BET-Y1Q4-T3-01)."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from omo.omo_autonomy_level import (
    AUTONOMY_LEVELS,
    AutonomyLadder,
    CapabilityAutonomy,
    PROMOTION_CRITERIA,
)


@pytest.fixture
def ladder(tmp_path: Path) -> AutonomyLadder:
    registry = tmp_path / "autonomy-levels.yaml"
    return AutonomyLadder(registry_path=registry)


class TestCapabilityAutonomy:
    def test_default_is_l0(self, ladder: AutonomyLadder) -> None:
        cap = ladder.get("test-cap")
        assert cap.level == "L0"
        assert cap.observations == 0

    def test_from_dict(self) -> None:
        cap = CapabilityAutonomy.from_dict(
            "x",
            {
                "level": "L2",
                "observations": 50,
                "consecutive_accepted": 30,
                "calibration": 0.6,
            },
        )
        assert cap.level == "L2"
        assert cap.observations == 50


class TestPromotion:
    def test_l0_to_l1_after_20_observations(self, ladder: AutonomyLadder) -> None:
        for i in range(25):
            ladder.record_adjudication("cap-a", "accepted")
        cap = ladder.get("cap-a")
        assert cap.level == "L1"
        assert cap.observations == 25

    def test_l0_stays_at_l0_below_20(self, ladder: AutonomyLadder) -> None:
        for i in range(19):
            ladder.record_adjudication("cap-b", "accepted")
        assert ladder.get("cap-b").level == "L0"

    def test_l1_to_l2_with_calibration_and_consecutive(
        self, ladder: AutonomyLadder
    ) -> None:
        ladder._data["capabilities"]["cap-c"] = {
            "level": "L1",
            "observations": 35,
            "total_accepted": 28,
            "consecutive_accepted": 29,
            "calibration": 0.8,
            "last_adjudication": "",
            "updated_at": "",
        }
        result = ladder.record_adjudication("cap-c", "accepted")
        assert result["level_changed"] is True
        assert result["to_level"] == "L2"

    def test_l1_stays_when_consecutive_too_low(self, ladder: AutonomyLadder) -> None:
        ladder._data["capabilities"]["cap-d"] = {
            "level": "L1",
            "observations": 100,
            "total_accepted": 70,
            "consecutive_accepted": 10,
            "calibration": 0.7,
            "last_adjudication": "",
            "updated_at": "",
        }
        result = ladder.record_adjudication("cap-d", "accepted")
        assert result.get("level_changed", False) is False
        assert ladder.get("cap-d").level == "L1"

    def test_l2_to_l3_with_high_calibration(self, ladder: AutonomyLadder) -> None:
        ladder._data["capabilities"]["cap-e"] = {
            "level": "L2",
            "observations": 110,
            "total_accepted": 100,
            "consecutive_accepted": 99,
            "calibration": 0.90,
            "last_adjudication": "",
            "updated_at": "",
        }
        result = ladder.record_adjudication("cap-e", "accepted")
        assert result["level_changed"] is True
        assert result["to_level"] == "L3"


class TestDemotion:
    def test_rejected_demotes_to_l0(self, ladder: AutonomyLadder) -> None:
        ladder._data["capabilities"]["cap-f"] = {
            "level": "L2",
            "observations": 80,
            "total_accepted": 60,
            "consecutive_accepted": 50,
            "calibration": 0.75,
            "last_adjudication": "",
            "updated_at": "",
        }
        result = ladder.record_adjudication("cap-f", "rejected")
        assert result["level_changed"] is True
        assert result["to_level"] == "L0"
        assert result["from_level"] == "L2"

    def test_rejected_at_l0_no_change(self, ladder: AutonomyLadder) -> None:
        result = ladder.record_adjudication("cap-g", "rejected")
        assert result.get("level_changed", False) is False
        assert ladder.get("cap-g").level == "L0"

    def test_rejected_resets_consecutive(self, ladder: AutonomyLadder) -> None:
        for _ in range(10):
            ladder.record_adjudication("cap-h", "accepted")
        assert ladder.get("cap-h").consecutive_accepted == 10
        ladder.record_adjudication("cap-h", "rejected")
        assert ladder.get("cap-h").consecutive_accepted == 0


class TestSnapshot:
    def test_snapshot_empty(self, ladder: AutonomyLadder) -> None:
        assert ladder.snapshot() == {}

    def test_snapshot_after_adjudications(self, ladder: AutonomyLadder) -> None:
        ladder.record_adjudication("cap-x", "accepted")
        ladder.record_adjudication("cap-y", "rejected")
        snap = ladder.snapshot()
        assert "cap-x" in snap
        assert "cap-y" in snap
        assert snap["cap-x"]["level"] == "L0"
        assert snap["cap-y"]["consecutive_accepted"] == 0


class TestCriteriaConstants:
    def test_four_levels(self) -> None:
        assert AUTONOMY_LEVELS == ("L0", "L1", "L2", "L3")

    def test_promotion_criteria_defined(self) -> None:
        assert "L0" in PROMOTION_CRITERIA
        assert "L1" in PROMOTION_CRITERIA
        assert "L2" in PROMOTION_CRITERIA
        assert PROMOTION_CRITERIA["L0"]["min_observations"] == 20
        assert PROMOTION_CRITERIA["L1"]["min_calibration"] == 0.6
        assert PROMOTION_CRITERIA["L2"]["min_calibration"] == 0.85


class TestDriftMonitoring:
    """Tests for drift monitoring and human review gate (BET-Y2Q3-T3-02)."""

    def test_windowed_calibration(self, ladder: AutonomyLadder) -> None:
        cap = CapabilityAutonomy(capability="test-cap")
        cap.recent_verdicts = ["accepted"] * 8 + ["rejected"] * 2
        assert cap.windowed_calibration() == 0.8

    def test_drift_triggers_demotion(self, ladder: AutonomyLadder) -> None:
        # Promote to L1 first
        for _ in range(25):
            ladder.record_adjudication("cap-a", "accepted")
        assert ladder.get("cap-a").level == "L1"

        # Now add poor recent performance to trigger drift
        cap = ladder.get("cap-a")
        cap.recent_verdicts = ["rejected"] * 20  # 0% windowed cal < 0.40 threshold
        ladder._save(cap)

        # Next adjudication should trigger drift demotion
        result = ladder.record_adjudication("cap-a", "accepted")
        assert result["level_changed"] is True
        assert result["to_level"] == "L0"
        assert "drift detected" in result["reason"]

    def test_human_review_blocks_promotion(self, ladder: AutonomyLadder) -> None:
        # Promote to L1
        for _ in range(25):
            ladder.record_adjudication("cap-b", "accepted")
        assert ladder.get("cap-b").level == "L1"

        # Trigger demotion via rejection
        ladder.record_adjudication("cap-b", "rejected")
        assert ladder.get("cap-b").level == "L0"
        assert ladder.get("cap-b").requires_human_review is True

        # Now add many accepted — should NOT promote due to human review flag
        for _ in range(30):
            ladder.record_adjudication("cap-b", "accepted")
        assert ladder.get("cap-b").level == "L0"  # Still L0

    def test_clear_human_review_allows_promotion(self, ladder: AutonomyLadder) -> None:
        # Promote to L1 then demote
        for _ in range(25):
            ladder.record_adjudication("cap-c", "accepted")
        ladder.record_adjudication("cap-c", "rejected")
        assert ladder.get("cap-c").requires_human_review is True

        # Clear human review flag
        result = ladder.clear_human_review("cap-c")
        assert result["cleared"] is True
        assert ladder.get("cap-c").requires_human_review is False

        # Now promotion should work — will promote to L2 (has enough observations)
        for _ in range(30):
            ladder.record_adjudication("cap-c", "accepted")
        assert ladder.get("cap-c").level == "L2"  # Promoted past L1 to L2

    def test_drift_needs_minimum_window(self, ladder: AutonomyLadder) -> None:
        # Promote to L1
        for _ in range(25):
            ladder.record_adjudication("cap-d", "accepted")
        assert ladder.get("cap-d").level == "L1"

        # Manually set recent_verdicts to small window (below min_window=20)
        cap = ladder.get("cap-d")
        cap.recent_verdicts = ["modified"] * 5  # Only 5 verdicts, below min_window
        ladder._save(cap)

        # Next adjudication should NOT trigger drift (window too small)
        ladder.record_adjudication("cap-d", "accepted")
        assert ladder.get("cap-d").level == "L1"  # Still L1, no drift demotion


def test_promotion_emits_level_change_event(ladder: AutonomyLadder, monkeypatch) -> None:
    """done_when: 升级产生一条 OMO 事件 (autonomy.level_change)."""
    import omo.omo_autonomy_level as mod

    events: list[tuple[str, str, str]] = []
    monkeypatch.setattr(
        mod, "_emit_event",
        lambda cap, frm, to, reason: events.append((cap, frm, to)),
    )

    for _ in range(20):
        ladder.record_adjudication("cap-e", "accepted")
    assert ladder.get("cap-e").level == "L1"
    assert any(cap == "cap-e" and frm == "L0" and to == "L1" for cap, frm, to in events)


def test_demotion_emits_level_change_event(ladder: AutonomyLadder, monkeypatch) -> None:
    """done_when: 降级产生一条 OMO 事件 (autonomy.level_change)."""
    import omo.omo_autonomy_level as mod

    events: list[tuple[str, str, str]] = []
    monkeypatch.setattr(
        mod, "_emit_event",
        lambda cap, frm, to, reason: events.append((cap, frm, to)),
    )

    for _ in range(20):
        ladder.record_adjudication("cap-f", "accepted")
    ladder.record_adjudication("cap-f", "rejected")
    assert ladder.get("cap-f").level == "L0"
    assert any(cap == "cap-f" and frm == "L1" and to == "L0" for cap, frm, to in events)
