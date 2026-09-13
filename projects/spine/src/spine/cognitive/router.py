"""MindModelRouter — SceneWatcher-driven routing based on quartet state."""

from __future__ import annotations

import time
from typing import Any

from spine.cognitive.store import MindModelStore


class MindModelRouter:
    """Routes decisions based on current mind model state.

    Circuit breaker: on any parse/validation error, fall back to static defaults.
    """

    def __init__(self, store: MindModelStore | None = None) -> None:
        self.store = store or MindModelStore()

    def _safe_read(self, dimension: str) -> dict[str, Any]:
        try:
            return self.store.read(dimension)
        except Exception:
            return {}

    def route(self, context: dict[str, Any] | None = None) -> dict[str, Any]:
        """Return routing directives based on quartet state. Must complete <= 500ms."""
        start = time.monotonic()

        persona = self._safe_read("persona_profile")
        agenda = self._safe_read("agenda_radar")
        attention = self._safe_read("attention_field")
        anchor = self._safe_read("context_anchor")

        elapsed_ms = (time.monotonic() - start) * 1000

        return {
            "tone": persona.get("tone", "neutral"),
            "verbosity": persona.get("verbosity", "balanced"),
            "priority_axis": agenda.get("priority_axis", "impact-first"),
            "info_density": attention.get("info_density", "medium"),
            "baseline_mood": anchor.get("baseline_mood", "focused"),
            "cognitive_load": anchor.get("cognitive_load", "moderate"),
            "elapsed_ms": round(elapsed_ms, 2),
            "circuit_breaker_ok": True,
        }
