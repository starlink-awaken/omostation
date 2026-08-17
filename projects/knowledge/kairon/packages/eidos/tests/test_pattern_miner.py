"""Tests for PatternMiner -- sequence and temporal pattern detection."""
# mock-heavy test: monkeypatch + dynamic attributes.
# pyright: reportAttributeAccessIssue=false

from eidos.memory.pattern_miner import (
    Pattern,
    PatternMiner,
    PatternType,
    SequencePattern,
    TemporalPattern,
)


class TestPatternDataClasses:
    def test_pattern_to_dict(self):
        p = Pattern(
            pattern_id="p-1",
            pattern_type=PatternType.CORRELATION,
            events=["a", "b"],
            frequency=5,
            confidence=0.8,
        )
        d = p.to_dict()
        assert d["pattern_id"] == "p-1"
        assert len(d["events"]) == 2

    def test_sequence_pattern_to_dict(self):
        sp = SequencePattern(
            pattern_id="sp-1",
            steps=["a", "b", "c"],
            min_support=0.3,
            occurrences=5,
            confidence=0.9,
        )
        d = sp.to_dict()
        assert len(d["steps"]) == 3
        assert d["min_support"] == 0.3

    def test_temporal_pattern_to_dict(self):
        tp = TemporalPattern(
            pattern_id="tp-1",
            event_type="click",
            time_distribution={"morning": 3.0, "evening": 2.0},  # type: ignore[reportArgumentType]
            peak_hours=[9],
            confidence=0.7,
        )
        d = tp.to_dict()
        assert d["event_type"] == "click"
        assert d["peak_hours"] == [9]
        assert len(d["time_distribution"]) == 2


class TestPatternMiner:
    def setup_method(self):
        self.miner = PatternMiner()

    def test_new_id(self):
        ids = {self.miner._new_id() for _ in range(100)}
        assert len(ids) == 100

    def test_event_key_from_object(self):
        class FakeEvent:
            def __init__(self):
                self.type = "test_type"

        assert self.miner._event_key(FakeEvent()) == "test_type"

    def test_event_key_from_dict(self):
        assert self.miner._event_key({"type": "click"}) == "click"

    def test_event_key_from_string(self):
        assert self.miner._event_key("raw-event") == "raw-event"

    def test_calculate_support(self):
        events = ["a", "b", "c", "a", "b"]
        pat = ["a", "b"]
        support = self.miner._calculate_support(pat, events)
        assert 0.0 < support <= 1.0

    def test_calculate_confidence_pattern(self):
        conf = self.miner._calculate_confidence(
            Pattern(
                pattern_id="p",
                pattern_type=PatternType.FREQUENCY,
                events=["a"],
                frequency=50,
                confidence=0.0,
            ),
            total_events=100,
        )
        # base = 50/100 = 0.5; min(1.0, 0.5 * sqrt(50)) = 1.0
        assert conf == 1.0

    def test_calculate_confidence_zero_events(self):
        conf = self.miner._calculate_confidence(
            Pattern(pattern_id="p", pattern_type=PatternType.FREQUENCY, events=["a"], frequency=0, confidence=0.0),
            total_events=0,
        )
        assert conf == 0.0

    def test_is_subsequence(self):
        assert self.miner._is_subsequence(["a", "b"], ["x", "a", "y", "b", "z"])
        assert not self.miner._is_subsequence(["a", "b"], ["b", "a"])

    def test_mine_patterns_empty(self):
        results = self.miner.mine_patterns([])
        assert results == []

    def test_mine_patterns_single_event(self):
        results = self.miner.mine_patterns(["click"])
        assert results == []

    def test_mine_patterns_with_events(self):
        events = ["login", "search", "view", "login", "search", "view", "login"]
        results = self.miner.mine_patterns(events)
        assert isinstance(results, list)
        # with 7 events of 3 types, should find some patterns
        assert len(results) > 0

    def test_detect_sequence_patterns_none(self):
        assert self.miner.detect_sequence_patterns([]) == []
        assert self.miner.detect_sequence_patterns(["a"]) == []

    def test_detect_sequence_patterns_basic(self):
        events = ["a", "b", "a", "b", "a", "b"]
        seqs = self.miner.detect_sequence_patterns(events)
        assert isinstance(seqs, list)

    def test_validate_access(self):
        assert self.miner.validate_access("mine", {}) is True

    def test_get_metadata(self):
        meta = self.miner.get_metadata()
        assert "name" in meta
        assert "status" in meta
