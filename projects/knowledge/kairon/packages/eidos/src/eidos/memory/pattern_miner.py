from __future__ import annotations

"""
---
Type: Module
Status: ACTIVE
Version: 1.0.0
Authority: nucleus/Z-Core/L0-Genome/R0-ACT-SYS-AX01-10_holographic_metadata_axiom.md
Layer: L3
---
"""
"""Pattern mining for behavior and event sequence analysis in D-Memory.

---
Type: Organ
Layer: L3
Domain: D-Memory
Status: ACTIVE
Version: 1.0.0
Authority: organs/D-Memory/AGENTS.md
Keywords: [pattern, mining, sequence, temporal, correlation, frequency, discovery]
---

# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# PatternMiner ≡ Organ
# 内涵 ≝ {pattern_id, pattern_type, events, frequency, confidence, discovered_at}
# 外延 ⊢ {p | p ∈ D-Memory ∧ pattern_discovered(p)}
# 功能 ⊢ {MinePatterns, DetectSequencePatterns, DetectTemporalPatterns,
#          CalculateSupport, CalculateConfidence}
# =============================================================================

Discovers statistical and temporal patterns from event streams.
Used by preference learning and habit detection.

Usage::

    miner = PatternMiner()
    patterns = miner.mine_patterns(events, min_frequency=3)
    seqs = miner.detect_sequence_patterns(events, window_size=10)
    temporals = miner.detect_temporal_patterns(events)
"""

import logging
import math
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, TypedDict, cast

_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Pattern type enum
# ---------------------------------------------------------------------------


class PatternType(StrEnum):
    """Classification of discovered patterns."""

    SEQUENCE = "sequence"  # Ordered event sequences
    TEMPORAL = "temporal"  # Time-of-day / day-of-week patterns
    CORRELATION = "correlation"  # Co-occurrence across event types
    FREQUENCY = "frequency"  # Simple frequency counts


# ---------------------------------------------------------------------------
# Core dataclasses
# ---------------------------------------------------------------------------


class PatternMetrics(TypedDict, total=False):
    """Extended evaluation metrics for a Pattern."""

    support: float
    confidence: float
    lift: float
    frequency: int


@dataclass
class Pattern:
    """A discovered pattern with evaluation metrics."""

    pattern_id: str
    pattern_type: PatternType
    events: list[Any]
    frequency: int
    confidence: float
    discovered_at: datetime = field(default_factory=datetime.now)
    metrics: PatternMetrics = field(default_factory=lambda: PatternMetrics())

    def to_dict(self) -> dict[str, Any]:
        return {
            "pattern_id": self.pattern_id,
            "pattern_type": self.pattern_type.value,
            "events": self.events,
            "frequency": self.frequency,
            "confidence": self.confidence,
            "discovered_at": self.discovered_at.isoformat(),
            "metrics": self.metrics,
        }


@dataclass
class SequencePattern:
    """An ordered sequence of events that recurs."""

    pattern_id: str
    steps: list[Any]
    min_support: float
    variance: float = 0.0
    avg_interval_seconds: float | None = None
    occurrences: int = 0
    confidence: float = 0.0
    discovered_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "pattern_id": self.pattern_id,
            "steps": self.steps,
            "min_support": self.min_support,
            "variance": self.variance,
            "avg_interval_seconds": self.avg_interval_seconds,
            "occurrences": self.occurrences,
            "confidence": self.confidence,
            "discovered_at": self.discovered_at.isoformat(),
        }


@dataclass
class TemporalPattern:
    """A time-of-day / recurring pattern."""

    pattern_id: str
    event_type: Any
    time_distribution: dict[int, int]  # hour -> count
    peak_hours: list[int] = field(default_factory=list)
    recurring_days: list[int] = field(default_factory=list)  # 0=Mon ... 6=Sun
    confidence: float = 0.0
    discovered_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "pattern_id": self.pattern_id,
            "event_type": self.event_type,
            "time_distribution": self.time_distribution,
            "peak_hours": self.peak_hours,
            "recurring_days": self.recurring_days,
            "confidence": self.confidence,
            "discovered_at": self.discovered_at.isoformat(),
        }


# ---------------------------------------------------------------------------
# PatternMiner
# ---------------------------------------------------------------------------


class PatternMiner:
    """Mining engine for behavior and event patterns.

    Discovers sequence, temporal, correlation, and frequency patterns
    from a stream of events. Designed for use by preference learning
    and habit detection systems.

    BOS-URI endpoints
    -----------------
    ``bos://memory/patterns/mine``       — mine all pattern types
    ``bos://memory/patterns/sequences``    — detect sequence patterns
    ``bos://memory/patterns/temporal``     — detect temporal patterns
    ``bos://memory/patterns/frequency``    — frequency analysis
    """

    def __init__(
        self,
        metadata_path: str = "organs/D-Memory/organs/pattern_miner.py",
    ) -> None:
        self.status = "ACTIVE"
        self._pattern_counter = 0
        _log.info("PatternMiner initialised")

    # -------------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------------

    def _new_id(self) -> str:
        self._pattern_counter += 1
        return f"pattern_{self._pattern_counter}_{int(datetime.now(UTC).timestamp())}"

    def _event_key(self, event: Any) -> str:
        """Extract a comparable string key from an event."""
        if isinstance(event, dict):
            return event.get("type", "") or str(event.get("action", ""))
        if hasattr(event, "type"):
            return str(event.type)
        return str(event)

    def _calculate_support(self, pattern_events: list[Any], all_events: list[Any]) -> float:
        """Compute support = fraction of windows containing the pattern."""
        if not all_events:
            return 0.0

        window_size = max(1, len(pattern_events))
        total_windows = max(1, len(all_events) - window_size + 1)
        pattern_keys = [self._event_key(e) for e in pattern_events]

        hits = 0
        for i in range(len(all_events) - window_size + 1):
            window_keys = [self._event_key(e) for e in all_events[i : i + window_size]]
            # Check subsequence
            if self._is_subsequence(pattern_keys, window_keys):
                hits += 1

        return hits / total_windows

    def _is_subsequence(self, pattern: list[str], window: list[str]) -> bool:
        """Check if pattern keys appear in order within the window."""
        j = 0
        for w in window:
            if j < len(pattern) and w == pattern[j]:
                j += 1
        return j == len(pattern)

    def _calculate_confidence(self, pattern: SequencePattern | Pattern, total_events: int) -> float:
        """Compute confidence as a function of support and occurrence count."""
        if total_events == 0:
            return 0.0
        if isinstance(pattern, SequencePattern):
            raw = (pattern.min_support * pattern.occurrences) / max(1, pattern.occurrences)
            return min(1.0, raw * math.log1p(pattern.occurrences) / math.log1p(total_events))
        # Pattern dataclass
        base = pattern.frequency / max(1, total_events)
        return min(1.0, base * math.sqrt(pattern.frequency))

    def _calculate_lift(self, pattern: SequencePattern | Pattern) -> float:
        """Compute lift = support(A,B) / (support(A) * support(B)).

        Lift > 1 indicates a positive correlation between pattern elements.
        Lift = 0 when support is undefined.
        """
        if isinstance(pattern, SequencePattern):
            support = pattern.min_support
        else:
            support = pattern.metrics.get("support", 0.0)
        if support == 0.0:
            return 0.0
        # Assuming independent baseline of 1 / |event space| (uniform)
        baseline = 1.0 / max(1, getattr(pattern, "frequency", 1))
        return support / (baseline * baseline) if baseline > 0 else 0.0

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    def mine_patterns(
        self,
        events: list[Any],
        min_frequency: int = 3,
    ) -> list[Pattern]:
        """Discover all pattern types from an event stream.

        Parameters
        ----------
        events:
            Chronologically ordered list of events.
        min_frequency:
            Minimum number of occurrences to qualify as a pattern.

        Returns
        -------
        list[Pattern]
            All discovered patterns across SEQUENCE, TEMPORAL, CORRELATION,
            and FREQUENCY types.
        """
        if not events or len(events) < 2:
            return []

        patterns: list[Pattern] = []
        total = len(events)

        # Frequency patterns — most common event types
        event_keys = [self._event_key(e) for e in events]
        freq_counter: Counter[str] = Counter(event_keys)
        for key, count in freq_counter.items():
            if count >= min_frequency:
                patterns.append(
                    Pattern(
                        pattern_id=self._new_id(),
                        pattern_type=PatternType.FREQUENCY,
                        events=[key],
                        frequency=count,
                        confidence=min(1.0, count / total),
                        metrics=PatternMetrics(
                            support=count / total, confidence=min(1.0, count / total), lift=1.0, frequency=count
                        ),
                    )
                )

        # Sequence patterns
        seqs = self.detect_sequence_patterns(events, window_size=10)
        for seq in seqs:
            if seq.occurrences >= min_frequency:
                patterns.append(
                    Pattern(
                        pattern_id=seq.pattern_id,
                        pattern_type=PatternType.SEQUENCE,
                        events=seq.steps,
                        frequency=seq.occurrences,
                        confidence=seq.confidence,
                        metrics=PatternMetrics(
                            support=seq.min_support, confidence=seq.confidence, lift=1.0, frequency=seq.occurrences
                        ),
                    )
                )

        # Temporal patterns
        temporals = self.detect_temporal_patterns(events)
        for tp in temporals:
            if tp.confidence > 0.0:
                patterns.append(
                    Pattern(
                        pattern_id=tp.pattern_id,
                        pattern_type=PatternType.TEMPORAL,
                        events=[tp.event_type],
                        frequency=sum(tp.time_distribution.values()),
                        confidence=tp.confidence,
                        metrics=PatternMetrics(
                            support=tp.confidence,
                            confidence=tp.confidence,
                            lift=1.0,
                            frequency=sum(tp.time_distribution.values()),
                        ),
                    )
                )

        # Correlation patterns — events that co-occur in overlapping time windows
        correlations = self._mine_correlations(events, min_frequency)
        patterns.extend(correlations)

        _log.info(
            "[PatternMiner] mined %d patterns from %d events (min_freq=%d)",
            len(patterns),
            total,
            min_frequency,
        )
        return patterns

    def detect_sequence_patterns(
        self,
        events: list[Any],
        window_size: int = 10,
    ) -> list[SequencePattern]:
        """Detect recurring ordered sequences in an event stream.

        Parameters
        ----------
        events:
            Chronologically ordered list of events.
        window_size:
            Maximum window for sequence matching.

        Returns
        -------
        list[SequencePattern]
            Discovered sequential patterns.
        """
        if not events or len(events) < 2:
            return []

        # Slide windows and collect n-gram sequences
        seq_counter: Counter[tuple] = Counter()
        for size in range(2, min(window_size + 1, len(events) + 1)):
            for i in range(len(events) - size + 1):
                window = tuple(self._event_key(e) for e in events[i : i + size])
                if len(set(window)) > 1:  # Discard trivial single-event "sequences"
                    seq_counter[window] += 1

        patterns: list[SequencePattern] = []
        total = len(events)

        for seq_tuple, count in seq_counter.items():
            if count < 2:
                continue
            support = self._calculate_support(list(seq_tuple), events)
            confidence = min(1.0, support * math.log1p(count) / math.log1p(total))
            patterns.append(
                SequencePattern(
                    pattern_id=self._new_id(),
                    steps=list(seq_tuple),
                    min_support=support,
                    occurrences=count,
                    confidence=confidence,
                )
            )

        patterns.sort(key=lambda p: p.confidence, reverse=True)
        return patterns

    def detect_temporal_patterns(
        self,
        events: list[Any],
    ) -> list[TemporalPattern]:
        """Detect time-of-day and day-of-week recurring patterns.

        Parameters
        ----------
        events:
            List of events. Events with a ``timestamp`` attribute or key
            are used for temporal analysis.

        Returns
        -------
        list[TemporalPattern]
            Discovered temporal patterns.
        """
        if not events:
            return []

        # Group events by type and collect timestamps
        type_times: dict[str, list[datetime]] = defaultdict(list)
        for event in events:
            ts = self._extract_timestamp(event)
            if ts is None:
                continue
            key = self._event_key(event)
            type_times[key].append(ts)

        patterns: list[TemporalPattern] = []
        for event_type, timestamps in type_times.items():
            if len(timestamps) < 2:
                continue

            # Hour distribution
            hour_counts: Counter[int] = Counter(t.hour for t in timestamps)
            time_dist = dict(hour_counts)

            # Peak hours — those above 1 std deviation from mean
            if hour_counts:
                mean = sum(hour_counts.keys()) / len(hour_counts)
                std = math.sqrt(sum((h - mean) ** 2 for h in hour_counts) / len(hour_counts))
                threshold = mean + std if std > 0 else mean
                peak_hours = sorted(h for h, c in hour_counts.items() if c > threshold)
            else:
                peak_hours = []

            # Recurring days
            day_counts = Counter(t.weekday() for t in timestamps)
            recurring_days = sorted(d for d, c in day_counts.items() if c >= 2)

            # Confidence: inverse entropy of hour distribution
            total_ts = len(timestamps)
            entropy = -sum((c / total_ts) * math.log2(c / total_ts) for c in hour_counts.values())
            max_entropy = math.log2(max(1, len(hour_counts)))
            confidence = 1.0 - (entropy / max_entropy) if max_entropy > 0 else 0.0

            patterns.append(
                TemporalPattern(
                    pattern_id=self._new_id(),
                    event_type=event_type,
                    time_distribution=time_dist,
                    peak_hours=peak_hours[:5],
                    recurring_days=recurring_days,
                    confidence=round(confidence, 4),
                )
            )

        return patterns

    # -------------------------------------------------------------------------
    # Internal correlation mining
    # -------------------------------------------------------------------------

    def _mine_correlations(
        self,
        events: list[Any],
        min_frequency: int,
    ) -> list[Pattern]:
        """Detect co-occurrence correlations between event types."""
        if len(events) < 4:
            return []

        # Pairwise co-occurrence within sliding windows
        window = 5
        pair_counts: Counter[tuple[str, str]] = Counter()
        for i in range(len(events) - 1):
            key_i = self._event_key(events[i])
            for j in range(i + 1, min(len(events), i + window)):
                key_j = self._event_key(events[j])
                if key_i != key_j:
                    pair: tuple[str, str] = cast(tuple[str, str], tuple(sorted([key_i, key_j])))
                    pair_counts[pair] += 1

        patterns: list[Pattern] = []
        for (k1, k2), count in pair_counts.items():
            if count >= min_frequency:
                support = count / max(1, len(events))
                patterns.append(
                    Pattern(
                        pattern_id=self._new_id(),
                        pattern_type=PatternType.CORRELATION,
                        events=[k1, k2],
                        frequency=count,
                        confidence=round(min(1.0, support * math.sqrt(count)), 4),
                        metrics=PatternMetrics(
                            support=support,
                            confidence=round(min(1.0, support * math.sqrt(count)), 4),
                            lift=1.0,
                            frequency=count,
                        ),
                    )
                )

        return patterns

    # -------------------------------------------------------------------------
    # Timestamp extraction
    # -------------------------------------------------------------------------

    def _extract_timestamp(self, event: Any) -> datetime | None:
        """Extract a datetime from an event object."""
        if isinstance(event, dict):
            ts = event.get("timestamp") or event.get("created_at")
        elif hasattr(event, "timestamp"):
            ts = event.timestamp
        elif hasattr(event, "created_at"):
            ts = event.created_at
        else:
            ts = None

        if ts is None:
            return None
        if isinstance(ts, datetime):
            return ts.replace(tzinfo=UTC) if ts.tzinfo is None else ts
        if isinstance(ts, (int, float)):
            return datetime.fromtimestamp(ts, tz=UTC)
        if isinstance(ts, str):
            try:
                return datetime.fromisoformat(ts.replace("Z", "+00:00"))
            except ValueError:
                return None
        return None

    # Required by CoreService
    def validate_access(self, _operation: str, _context: dict[str, Any]) -> bool:
        return True

    def get_metadata(self) -> dict[str, Any]:
        return {
            "name": "PatternMiner",
            "domain": "D-Memory",
            "layer": "L3",
            "version": "1.0.0",
            "status": self.status,
        }

    def get_registry_info(self) -> dict[str, Any]:
        return {
            "bos_uri": "bos://memory/patterns",
            "endpoints": [
                "bos://memory/patterns/mine",
                "bos://memory/patterns/sequences",
                "bos://memory/patterns/temporal",
                "bos://memory/patterns/frequency",
            ],
        }
