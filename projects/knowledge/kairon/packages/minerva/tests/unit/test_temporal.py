"""Tests for TemporalReasoner — Allen interval algebra."""

from datetime import date


class TestTimeInterval:
    """Tests for TimeInterval."""

    def test_parse_yyyy_mm_dd(self):
        from minerva.knowledge.temporal import TimeInterval

        ti = TimeInterval.parse("2024-01-15,2024-12-31")
        assert ti is not None
        assert ti.start == date(2024, 1, 15)
        assert ti.end == date(2024, 12, 31)

    def test_parse_yyyy_mm(self):
        from minerva.knowledge.temporal import TimeInterval

        ti = TimeInterval.parse("2024-06,2025-03")
        assert ti is not None
        assert ti.start == date(2024, 6, 1)
        assert ti.end == date(2025, 3, 1)

    def test_parse_none(self):
        from minerva.knowledge.temporal import TimeInterval

        assert TimeInterval.parse(None) is None

    def test_duration_days(self):
        from minerva.knowledge.temporal import TimeInterval

        ti = TimeInterval(date(2024, 1, 1), date(2024, 1, 31))
        assert ti.duration_days == 30

    def test_contains(self):
        from minerva.knowledge.temporal import TimeInterval

        outer = TimeInterval(date(2020, 1, 1), date(2030, 1, 1))
        inner = TimeInterval(date(2024, 1, 1), date(2024, 12, 31))
        assert outer.contains(inner)
        assert not inner.contains(outer)

    def test_overlaps_with(self):
        from minerva.knowledge.temporal import TimeInterval

        a = TimeInterval(date(2024, 1, 1), date(2024, 6, 30))
        b = TimeInterval(date(2024, 3, 1), date(2024, 9, 30))
        c = TimeInterval(date(2024, 7, 1), date(2024, 12, 31))
        assert a.overlaps_with(b)
        assert not a.overlaps_with(c)


class TestTemporalReasoner:
    """Tests for Allen interval algebra relations."""

    def test_before(self):
        from minerva.knowledge.temporal import (
            AllenRelation,
            TemporalReasoner,
            TimeInterval,
        )

        reasoner = TemporalReasoner()
        a = TimeInterval(date(2020, 1, 1), date(2020, 6, 1))
        b = TimeInterval(date(2021, 1, 1), date(2021, 6, 1))
        assert reasoner.relate(a, b) == AllenRelation.BEFORE
        assert reasoner.relate(b, a) == AllenRelation.AFTER

    def test_meets(self):
        from minerva.knowledge.temporal import (
            AllenRelation,
            TemporalReasoner,
            TimeInterval,
        )

        reasoner = TemporalReasoner()
        a = TimeInterval(date(2020, 1, 1), date(2020, 6, 1))
        b = TimeInterval(date(2020, 6, 1), date(2020, 12, 1))
        assert reasoner.relate(a, b) == AllenRelation.MEETS
        assert reasoner.relate(b, a) == AllenRelation.MET_BY

    def test_overlaps(self):
        from minerva.knowledge.temporal import (
            AllenRelation,
            TemporalReasoner,
            TimeInterval,
        )

        reasoner = TemporalReasoner()
        a = TimeInterval(date(2020, 1, 1), date(2020, 9, 1))
        b = TimeInterval(date(2020, 6, 1), date(2020, 12, 1))
        assert reasoner.relate(a, b) == AllenRelation.OVERLAPS
        assert reasoner.relate(b, a) == AllenRelation.OVERLAPPED_BY

    def test_during_contains(self):
        from minerva.knowledge.temporal import (
            AllenRelation,
            TemporalReasoner,
            TimeInterval,
        )

        reasoner = TemporalReasoner()
        outer = TimeInterval(date(2020, 1, 1), date(2025, 1, 1))
        inner = TimeInterval(date(2022, 1, 1), date(2023, 1, 1))
        assert reasoner.relate(inner, outer) == AllenRelation.DURING
        assert reasoner.relate(outer, inner) == AllenRelation.CONTAINS

    def test_starts(self):
        from minerva.knowledge.temporal import (
            AllenRelation,
            TemporalReasoner,
            TimeInterval,
        )

        reasoner = TemporalReasoner()
        a = TimeInterval(date(2020, 1, 1), date(2020, 6, 1))
        b = TimeInterval(date(2020, 1, 1), date(2020, 12, 1))
        assert reasoner.relate(a, b) == AllenRelation.STARTS
        assert reasoner.relate(b, a) == AllenRelation.STARTED_BY

    def test_finishes(self):
        from minerva.knowledge.temporal import (
            AllenRelation,
            TemporalReasoner,
            TimeInterval,
        )

        reasoner = TemporalReasoner()
        a = TimeInterval(date(2020, 6, 1), date(2020, 12, 1))
        b = TimeInterval(date(2020, 1, 1), date(2020, 12, 1))
        assert reasoner.relate(a, b) == AllenRelation.FINISHES
        assert reasoner.relate(b, a) == AllenRelation.FINISHED_BY

    def test_equals(self):
        from minerva.knowledge.temporal import (
            AllenRelation,
            TemporalReasoner,
            TimeInterval,
        )

        reasoner = TemporalReasoner()
        a = TimeInterval(date(2020, 1, 1), date(2020, 12, 1))
        b = TimeInterval(date(2020, 1, 1), date(2020, 12, 1))
        assert reasoner.relate(a, b) == AllenRelation.EQUALS

    def test_is_valid_now(self):
        from minerva.knowledge.temporal import TemporalReasoner, TimeInterval

        reasoner = TemporalReasoner()
        cur = TimeInterval(
            date(2020, 1, 1),
            date(9999, 12, 31),
        )
        ref = date(2024, 6, 15)
        assert reasoner.is_valid_now(cur, ref) is True

    def test_is_stale(self):
        from minerva.knowledge.temporal import TemporalReasoner, TimeInterval

        reasoner = TemporalReasoner()
        old = TimeInterval(date(2020, 1, 1), date(2020, 6, 1))
        ref = date(2024, 6, 15)
        assert reasoner.is_stale(old, ref, stale_threshold_days=365) is True

    def test_is_not_stale_recent(self):
        from minerva.knowledge.temporal import TemporalReasoner, TimeInterval

        reasoner = TemporalReasoner()
        recent = TimeInterval(date(2024, 1, 1), date(2024, 6, 1))
        ref = date(2024, 6, 15)
        assert reasoner.is_stale(recent, ref, stale_threshold_days=365) is False

    def test_get_validity_status(self):
        from minerva.knowledge.temporal import TemporalReasoner, TimeInterval

        reasoner = TemporalReasoner()
        cur = TimeInterval(date(2020, 1, 1), date(9999, 12, 31))
        assert reasoner.get_validity_status(cur) == "CURRENT"

    def test_get_validity_status_expired(self):
        from minerva.knowledge.temporal import TemporalReasoner, TimeInterval

        reasoner = TemporalReasoner()
        old = TimeInterval(date(2020, 1, 1), date(2020, 6, 1))
        assert reasoner.get_validity_status(old) == "EXPIRED"


class TestAllenRelationEnum:
    """Test AllenRelation enum values."""

    def test_all_relations_present(self):
        from minerva.knowledge.temporal import AllenRelation

        values = {r.value for r in AllenRelation}
        expected = {
            "before",
            "after",
            "meets",
            "met_by",
            "overlaps",
            "overlapped_by",
            "during",
            "contains",
            "starts",
            "started_by",
            "finishes",
            "finished_by",
            "equals",
        }
        assert values == expected
