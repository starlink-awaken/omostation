"""Temporal reasoning — Allen interval algebra for knowledge validity.

Implements the 7 core Allen relations for temporal entity management:
- BEFORE / AFTER: Interval A ends before B starts
- MEETS / MET_BY: A ends exactly when B starts
- OVERLAPS / OVERLAPPED_BY: Intervals overlap but don't contain
- DURING / CONTAINS: One interval fully inside another
- STARTS / STARTED_BY: Same start, different end
- FINISHES / FINISHED_BY: Same end, different start
- EQUALS: Same start and end

Usage:
    reasoner = TemporalReasoner()
    result = reasoner.relate(
        ("2024-01", "2024-06"),  # GPT-4 valid period
        ("2024-03", "2024-09"),  # GPT-4o valid period
    )
    # result = "OVERLAPS"
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from enum import Enum


class AllenRelation(Enum):
    """Allen's 13 interval algebra relations."""

    BEFORE = "before"  # A before B
    AFTER = "after"  # A after B (BEFORE inverse)
    MEETS = "meets"  # A meets B
    MET_BY = "met_by"  # A met by B (MEETS inverse)
    OVERLAPS = "overlaps"  # A overlaps B
    OVERLAPPED_BY = "overlapped_by"  # OVERLAPS inverse
    DURING = "during"  # A during B
    CONTAINS = "contains"  # B during A (DURING inverse)
    STARTS = "starts"  # A starts with B
    STARTED_BY = "started_by"  # STARTS inverse
    FINISHES = "finishes"  # A finishes with B
    FINISHED_BY = "finished_by"  # FINISHES inverse
    EQUALS = "equals"  # A equals B


@dataclass
class TimeInterval:
    """A time interval with inclusive start and exclusive end."""

    start: date
    end: date

    @classmethod
    def parse(cls, value: str | None) -> TimeInterval | None:
        """Parse an interval from 'YYYY-MM-DD' or 'YYYY-MM' string pair."""
        if value is None:
            return None
        parts = str(value).split(",") if "," in str(value) else [str(value), "9999-12-31"]
        try:
            s = cls._to_date(parts[0].strip())
            e = cls._to_date(parts[1].strip())
            return cls(s, e)
        except (ValueError, IndexError):
            return None

    @staticmethod
    def _to_date(s: str) -> date:
        s = s.strip()
        if len(s) == 7:  # YYYY-MM
            year, month = int(s[:4]), int(s[5:7])
            return date(year, month, 1)
        return date.fromisoformat(s)

    @property
    def duration_days(self) -> int:
        return (self.end - self.start).days

    def contains(self, other: TimeInterval) -> bool:
        return self.start <= other.start and other.end <= self.end

    def overlaps_with(self, other: TimeInterval) -> bool:
        return self.start < other.end and other.start < self.end


class TemporalReasoner:
    """Allen interval algebra reasoner for knowledge validity checks.

    Given two time intervals (e.g., entity valid_from/valid_until),
    determines their temporal relation and whether knowledge is stale.
    """

    def relate(self, a: TimeInterval, b: TimeInterval) -> AllenRelation:
        """Determine the Allen relation between intervals a and b."""
        if a.start == b.start and a.end == b.end:
            return AllenRelation.EQUALS
        if a.start == b.start:
            return AllenRelation.STARTS if a.end < b.end else AllenRelation.STARTED_BY
        if a.end == b.end:
            return AllenRelation.FINISHES if a.start > b.start else AllenRelation.FINISHED_BY
        if a.end <= b.start:
            return AllenRelation.BEFORE if a.end < b.start else AllenRelation.MEETS
        if b.end <= a.start:
            return AllenRelation.AFTER if b.end < a.start else AllenRelation.MET_BY
        if a.contains(b):
            return AllenRelation.CONTAINS
        if b.contains(a):
            return AllenRelation.DURING
        if a.start < b.start:
            return AllenRelation.OVERLAPS
        return AllenRelation.OVERLAPPED_BY

    def is_valid_now(self, interval: TimeInterval, reference_date: date | None = None) -> bool:
        """Check if an interval is currently valid."""
        now = reference_date or date.today()
        return interval.start <= now <= interval.end

    def is_stale(
        self,
        interval: TimeInterval,
        reference_date: date | None = None,
        stale_threshold_days: int = 180,
    ) -> bool:
        """Check if knowledge ended more than stale_threshold_days ago."""
        now = reference_date or date.today()
        if interval.end >= now:
            return False  # Still valid
        return (now - interval.end).days > stale_threshold_days

    def relates_to_now(self, interval: TimeInterval) -> AllenRelation:
        """Return the Allen relation of an interval relative to today."""
        now = TimeInterval(
            start=date.today() - timedelta(days=1),
            end=date.today() + timedelta(days=1),
        )
        return self.relate(interval, now)

    def get_validity_status(self, interval: TimeInterval) -> str:
        """Human-readable validity status."""
        relation = self.relates_to_now(interval)
        mapping = {
            AllenRelation.CONTAINS: "CURRENT",
            AllenRelation.DURING: "CURRENT",
            AllenRelation.OVERLAPS: "CURRENT_EXPIRING_SOON",
            AllenRelation.OVERLAPPED_BY: "FUTURE",
            AllenRelation.AFTER: "FUTURE",
            AllenRelation.BEFORE: "EXPIRED",
            AllenRelation.MEETS: "EXPIRING",
            AllenRelation.MET_BY: "STARTING_SOON",
            AllenRelation.STARTS: "CURRENT",
            AllenRelation.FINISHES: "EXPIRING",
            AllenRelation.EQUALS: "CURRENT",
        }
        return mapping.get(relation, "UNKNOWN")
