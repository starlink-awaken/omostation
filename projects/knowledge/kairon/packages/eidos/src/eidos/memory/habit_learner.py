# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# HabitLearner ≡ Memory_Organ
# 内涵 ≝ {habit_id, habit_type, behavior_sequence, confidence, frequency}
# 外延 ≝ {h | h ∈ D-Memory ∧ learned(h)}
# 功能 ⊢ {learn_habits, detect_habit_formation, predict_next_action}
# =============================================================================

"""
---
Type: Organ
Layer: L3
Domain: D-Memory
Status: ACTIVE
Version: 1.0.0
Authority: organs/D-Memory/AGENTS.md
Keywords: [habit, learning, pattern, prediction, behavior, memory, fact_graph]
BOS-URI:
  - bos://memory/habit/learn       — learn_habits
  - bos://memory/habit/detect      — detect_habit_formation
  - bos://memory/habit/predict     — predict_next_action
  - bos://memory/habit/history     — get_habit_history
---
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, cast

_log = logging.getLogger(__name__)

# Default user when none specified
_DEFAULT_USER = "@Prime"

# ---------------------------------------------------------------------------
# HabitType enum
# ---------------------------------------------------------------------------


class HabitType(StrEnum):
    """Classification of recognized habit types."""

    DAILY_ROUTINE = "DAILY_ROUTINE"  # Repeats at same time each day
    WORKFLOW_HABIT = "WORKFLOW_HABIT"  # Sequence of tool/tool steps
    TOOL_PREFERENCE = "TOOL_PREFERENCE"  # Preference for a specific tool
    TEMPORAL_HABIT = "TEMPORAL_HABIT"  # Time-of-day or day-of-week patterns


# ---------------------------------------------------------------------------
# Habit dataclass
# ---------------------------------------------------------------------------


@dataclass
class Habit:
    """Represents a learned user habit.

    Attributes:
        habit_id: Unique identifier for this habit.
        habit_type: One of DAILY_ROUTINE, WORKFLOW_HABIT, TOOL_PREFERENCE, TEMPORAL_HABIT.
        behavior_sequence: Ordered list of actions/events that constitute the habit.
        confidence: A float in [0.0, 1.0] indicating how strongly this habit is established.
        first_seen: ISO-8601 timestamp of when the habit was first observed.
        last_seen: ISO-8601 timestamp of the most recent occurrence.
        frequency: Number of times the behavior sequence has been observed.
        user_id: Identifier of the user this habit belongs to.
        context: Additional metadata (e.g. time-of-day flags, device, location).
    """

    habit_id: str
    habit_type: HabitType
    behavior_sequence: list[str]
    confidence: float
    first_seen: str
    last_seen: str
    frequency: int
    user_id: str = _DEFAULT_USER
    context: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "habit_id": self.habit_id,
            "habit_type": self.habit_type.value,
            "behavior_sequence": self.behavior_sequence,
            "confidence": self.confidence,
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
            "frequency": self.frequency,
            "user_id": self.user_id,
            "context": self.context,
        }


# ---------------------------------------------------------------------------
# ActionPrediction dataclass
# ---------------------------------------------------------------------------


@dataclass
class ActionPrediction:
    """Prediction of the next likely action.

    Attributes:
        predicted_action: The most likely next action in the sequence.
        confidence: Confidence score in [0.0, 1.0].
        current_context: The context at the time of prediction.
        alternatives: Other possible next actions with their relative scores.
        habit_id: The habit from which this prediction was derived.
    """

    predicted_action: str
    confidence: float
    current_context: dict[str, Any]
    alternatives: dict[str, float]
    habit_id: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "predicted_action": self.predicted_action,
            "confidence": self.confidence,
            "current_context": self.current_context,
            "alternatives": self.alternatives,
            "habit_id": self.habit_id,
        }


# ---------------------------------------------------------------------------
# Pattern dataclass (simplified, mirrors pattern_miner output)
# ---------------------------------------------------------------------------


@dataclass
class Pattern:
    """A behavior pattern extracted by pattern_miner.

    This is the input interface expected from the upstream pattern_miner organ.
    In production this type may be imported from the pattern_miner module directly.
    """

    pattern_id: str
    events: list[str]
    frequency: int
    period_seconds: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# HabitLearner
# ---------------------------------------------------------------------------


class HabitLearner:
    """Learns and predicts user habits from behavioral patterns.

    Consumes ``Pattern`` objects produced by ``pattern_miner``, persists
    learned ``Habit`` objects to the ``FactGraph``, and exposes next-action
    predictions for downstream decision-making.

    BOS-URI endpoints
    ------------------
    ``bos://memory/habit/learn``     — learn_habits(patterns, user_id)
    ``bos://memory/habit/detect``     — detect_habit_formation(user_id, ...)
    ``bos://memory/habit/predict``   — predict_next_action(user_id, ...)
    ``bos://memory/habit/history``   — get_habits(user_id)

    Examples
    --------
    >>> learner = HabitLearner()
    >>> patterns = [
    ...     Pattern(pattern_id="p1", events=["open_editor", "write_code", "commit"], frequency=14),
    ... ]
    >>> habits = learner.learn_habits(patterns, user_id="@Prime")
    >>> pred = learner.predict_next_action("@Prime", {"step": "write_code"})
    >>> print(pred.predicted_action)
    """

    def __init__(self, user_id: str = _DEFAULT_USER) -> None:
        """Initialize the HabitLearner.

        Args:
            user_id: The user whose habits are being learned (default ``@Prime``).
        """
        self.user_id = user_id
        self._fact_graph = self._get_fact_graph()
        _log.debug("[HabitLearner] initialized for user=%s", self.user_id)

    # ------------------------------------------------------------------
    # FactGraph lazy initialization
    # ------------------------------------------------------------------

    def _get_fact_graph(self) -> Any | None:
        """Lazily load FactGraph to avoid circular import at startup."""
        try:
            from eidos.fact_graph import FactGraph

            return FactGraph()
        except ImportError:
            _log.warning("[HabitLearner] FactGraph unavailable — habits will not persist")
            return None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def learn_habits(
        self,
        patterns: list[Pattern | dict[str, Any]],
        user_id: str = _DEFAULT_USER,
    ) -> list[Habit]:
        """Convert behavior patterns into persistent habits.

        Args:
            patterns: List of ``Pattern`` objects (or dicts) from ``pattern_miner``.
            user_id: Owner of these habits.

        Returns:
            List of newly created or updated ``Habit`` objects.
        """
        uid = user_id or self.user_id
        now = self._now()
        habits: list[Habit] = []

        for raw in patterns:
            if isinstance(raw, dict):
                pat = Pattern(**raw)
            else:
                pat = raw

            confidence = self._calculate_confidence(pat)
            if confidence < 0.3:
                _log.debug(
                    "[HabitLearner] pattern %s confidence %.2f < 0.3, skipping",
                    pat.pattern_id,
                    confidence,
                )
                continue

            habit_type = self._infer_habit_type(pat)

            habit = Habit(
                habit_id=f"habit-{uuid.uuid4().hex[:12]}",
                habit_type=habit_type,
                behavior_sequence=pat.events,
                confidence=confidence,
                first_seen=now,
                last_seen=now,
                frequency=pat.frequency,
                user_id=uid,
                context=dict(pat.metadata or {}),
            )

            habits.append(habit)
            self._store_habit(habit)

            _log.info(
                "[HabitLearner] learned habit=%s type=%s confidence=%.2f",
                habit.habit_id,
                habit.habit_type.value,
                habit.confidence,
            )

        return habits

    def detect_habit_formation(
        self,
        user_id: str,
        behavior_sequence: list[str],
        threshold_days: int = 7,
    ) -> bool:
        """Detect whether a behavior sequence has become an established habit.

        A habit is considered formed when the same sequence appears at least
        ``threshold_days`` times within a rolling window.

        Args:
            user_id: The user to evaluate.
            behavior_sequence: The candidate behavior sequence.
            threshold_days: Minimum number of distinct days the sequence must
                appear to be considered a habit (default 7).

        Returns:
            True if the habit threshold is met, False otherwise.
        """
        uid = user_id or self.user_id
        stored = self._load_habits_for_user(uid)

        seq_key = tuple(behavior_sequence)
        matching = [h for h in stored if tuple(h.behavior_sequence) == seq_key and h.user_id == uid]

        if not matching:
            # Check if the sequence appears in recent pattern log
            return self._count_sequence_occurrences(uid, behavior_sequence) >= threshold_days

        # Re-evaluate confidence from stored habit
        top = max(matching, key=lambda h: h.frequency)
        return top.frequency >= threshold_days

    def predict_next_action(
        self,
        user_id: str,
        current_context: dict[str, Any],
    ) -> ActionPrediction:
        """Predict the most likely next action given the current context.

        Finds the most relevant habit and returns its implied next action,
        along with alternatives ranked by confidence.

        Args:
            user_id: The user to predict for.
            current_context: Must contain at least a ``step`` key indicating
                the current position in the behavior sequence.

        Returns:
            An ``ActionPrediction`` with the predicted next action and alternatives.
        """
        uid = user_id or self.user_id
        habits = self._load_habits_for_user(uid)

        if not habits:
            return ActionPrediction(
                predicted_action="unknown",
                confidence=0.0,
                current_context=current_context,
                alternatives={},
                habit_id="none",
            )

        current_step = current_context.get("step", "")
        candidates: list[tuple[Habit, int]] = []

        for habit in habits:
            try:
                idx = habit.behavior_sequence.index(current_step)
                # Only predict if not already at the end of the sequence
                if idx < len(habit.behavior_sequence) - 1:
                    candidates.append((habit, idx))
            except ValueError:
                continue

        if not candidates:
            # No exact match — return most frequent habit as fallback
            top = max(habits, key=lambda h: h.frequency)
            return ActionPrediction(
                predicted_action=top.behavior_sequence[-1] if top.behavior_sequence else "unknown",
                confidence=top.confidence * 0.5,
                current_context=current_context,
                alternatives={},
                habit_id=top.habit_id,
            )

        # Score candidates: prefer higher confidence and longer sequences
        scored = [
            (h, idx, h.confidence * (len(h.behavior_sequence) / max(len(h.behavior_sequence), 1)))
            for h, idx in candidates
        ]
        best_habit, best_idx, _ = max(scored, key=lambda x: x[2])

        next_action = best_habit.behavior_sequence[best_idx + 1]

        alternatives = {
            h.behavior_sequence[min(idx + 1, len(h.behavior_sequence) - 1)]: round(h.confidence, 3)
            for h, idx in candidates
            if h.habit_id != best_habit.habit_id
        }

        return ActionPrediction(
            predicted_action=next_action,
            confidence=best_habit.confidence,
            current_context=current_context,
            alternatives=alternatives,
            habit_id=best_habit.habit_id,
        )

    def get_habits(
        self,
        user_id: str | None = None,
        habit_type: HabitType | None = None,
        limit: int = 100,
    ) -> list[Habit]:
        """Retrieve stored habits for a user.

        Args:
            user_id: Filter by user (defaults to this instance's user).
            habit_type: Optional habit type filter.
            limit: Maximum number of habits to return.

        Returns:
            List of matching ``Habit`` objects.
        """
        uid = user_id or self.user_id
        habits = self._load_habits_for_user(uid)
        if habit_type is not None:
            habits = [h for h in habits if h.habit_type == habit_type]
        return sorted(habits, key=lambda h: h.confidence, reverse=True)[:limit]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _now() -> str:
        return datetime.now(UTC).isoformat()

    def _calculate_confidence(self, pattern: Pattern) -> float:
        """Calculate habit confidence from pattern characteristics.

        Confidence is a weighted combination of:
        - Frequency: how many times the pattern has been observed.
        - Consistency: how regular the pattern is (low variance in period).

        Returns:
            A float in [0.0, 1.0].
        """
        # Frequency component: log-scaled, maxed at 1.0
        freq_score = min(1.0, (pattern.frequency**0.5) / 5.0)

        # Consistency component: based on period regularity
        period_score = 0.5
        if pattern.period_seconds is not None and pattern.period_seconds > 0:
            # Ideal daily rhythm ≈ 86400 s; penalize large deviations
            ideal = 86400.0
            deviation = abs(pattern.period_seconds - ideal) / ideal
            period_score = max(0.0, 1.0 - deviation)

        return cast("float", round(freq_score * 0.6 + period_score * 0.4, 3))

    def _infer_habit_type(self, pattern: Pattern) -> HabitType:
        """Infer the most likely habit type from pattern metadata."""
        meta = pattern.metadata or {}
        hinted = meta.get("habit_type") or meta.get("type")
        if hinted:
            try:
                return HabitType(hinted.upper())
            except ValueError:
                pass

        # Infer from event content
        events_str = " ".join(pattern.events).lower()

        if any(word in events_str for word in ["morning", "afternoon", "evening", "daily", "wake"]):
            return HabitType.DAILY_ROUTINE
        if any(word in events_str for word in ["commit", "push", "merge", "review", "test", "deploy"]):
            return HabitType.WORKFLOW_HABIT
        if any(word in events_str for word in ["open", "close", "switch", "偏好", "prefer"]):
            return HabitType.TOOL_PREFERENCE
        if any(word in events_str for word in ["monday", "tuesday", "weekday", "weekend", "time"]):
            return HabitType.TEMPORAL_HABIT

        # Fallback: classify by sequence length
        if len(pattern.events) <= 2:
            return HabitType.TOOL_PREFERENCE
        if len(pattern.events) <= 5:
            return HabitType.WORKFLOW_HABIT
        return HabitType.DAILY_ROUTINE

    def _store_habit(self, habit: Habit) -> None:
        """Persist a habit to FactGraph."""
        fg = self._fact_graph
        if fg is None:
            _log.warning("[HabitLearner] FactGraph unavailable — habit not persisted")
            return

        try:
            fg.add_fact(
                sub=f"user:{habit.user_id}",
                pred=f"has_habit:{habit.habit_id}",
                obj=habit.habit_type.value,
                metadata=habit.to_dict(),
            )
            for i, event in enumerate(habit.behavior_sequence):
                fg.add_fact(
                    sub=f"habit:{habit.habit_id}",
                    pred=f"step:{i}",
                    obj=event,
                    metadata={"habit_id": habit.habit_id, "sequence_pos": i},
                )
            _log.debug("[HabitLearner] persisted habit %s to FactGraph", habit.habit_id)
        except (OSError, ConnectionError, AttributeError) as exc:
            _log.warning("[HabitLearner] failed to persist habit: %s", exc)

    def _load_habits_for_user(self, user_id: str) -> list[Habit]:
        """Load all habits for a user from FactGraph."""
        fg = self._fact_graph
        if fg is None:
            return []

        try:
            results = fg.query(sub=f"user:{user_id}")
            habits: list[Habit] = []
            for row in results:
                meta = row.get("metadata") or {}
                if isinstance(meta, dict) and "habit_id" in meta:
                    habits.append(Habit(**{k: v for k, v in meta.items() if k in Habit.__dataclass_fields__}))
            return habits
        except (OSError, ConnectionError, KeyError, AttributeError) as exc:
            _log.warning("[HabitLearner] failed to load habits: %s", exc)
            return []

    def _count_sequence_occurrences(
        self,
        _user_id: str,
        behavior_sequence: list[str],
    ) -> int:
        """Count how many distinct days a sequence appears in logs."""
        fg = self._fact_graph
        if fg is None:
            return 0

        try:
            seq_str = " → ".join(behavior_sequence)
            results = fg.query(pred="behavior_sequence", obj=seq_str)
            return len(results)
        except (OSError, ConnectionError, AttributeError):
            return 0

    # ------------------------------------------------------------------
    # BOS-URI handlers (CoreService.call dispatch)
    # ------------------------------------------------------------------

    def _handle_learn(self, params: dict[str, Any]) -> dict[str, Any]:
        patterns = params.get("patterns", [])
        user_id = params.get("user_id", _DEFAULT_USER)
        habits = self.learn_habits(patterns, user_id=user_id)
        return {"status": "ok", "habits": [h.to_dict() for h in habits]}

    def _handle_detect(self, params: dict[str, Any]) -> dict[str, Any]:
        user_id = params.get("user_id", _DEFAULT_USER)
        sequence = params.get("behavior_sequence", [])
        threshold = params.get("threshold_days", 7)
        formed = self.detect_habit_formation(user_id, sequence, threshold_days=threshold)
        return {"status": "ok", "habit_formed": formed}

    def _handle_predict(self, params: dict[str, Any]) -> dict[str, Any]:
        user_id = params.get("user_id", _DEFAULT_USER)
        context = params.get("current_context", {})
        pred = self.predict_next_action(user_id, context)
        return {"status": "ok", "prediction": pred.to_dict()}

    def _handle_history(self, params: dict[str, Any]) -> dict[str, Any]:
        user_id = params.get("user_id")
        habit_type = params.get("habit_type")
        limit = params.get("limit", 100)
        if habit_type is not None:
            habit_type = HabitType(habit_type)
        habits = self.get_habits(user_id=user_id, habit_type=habit_type, limit=limit)
        return {"status": "ok", "habits": [h.to_dict() for h in habits]}
