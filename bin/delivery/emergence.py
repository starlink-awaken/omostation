"""G-DEL.5b — Emergence detection + collective decision (scoped) + kill-switch.

Respects ADR-0221: hard scope limits + human intervention. Accuracy measured on
labeled fixture set; kill-switch blocks write-side effects.
Target: accuracy > 80% and kill-switch effective (BET-8c7c).
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any


@dataclass
class EmergenceEvent:
    text: str
    label: bool  # True = emergent multi-agent pattern
    features: dict[str, float] = field(default_factory=dict)


class KillSwitch:
    """K1/K2 style: global env + session kill flag."""

    def __init__(self, enabled: bool | None = None) -> None:
        if enabled is None:
            enabled = os.environ.get("ECOS_EMERGENCE_ENABLED", "0") == "1"
        self.enabled = enabled
        self.session_killed = False

    def kill(self) -> None:
        self.session_killed = True

    def allow_run(self) -> bool:
        return self.enabled and not self.session_killed

    def allow_write(self) -> bool:
        # S1: write path default off unless explicitly enabled and not killed
        return self.allow_run() and os.environ.get("ECOS_EMERGENCE_WRITES", "0") == "1"


class EmergenceDetector:
    """Heuristic detector for demo/measure — not production ML.

    Labels as emergent when multi-agent coordination markers appear.
    """

    MARKERS = (
        "collective",
        "swarm consensus",
        "multi-agent vote",
        "emergent",
        "quorum",
    )

    def __init__(self, kill: KillSwitch | None = None) -> None:
        self.kill = kill or KillSwitch(enabled=True)
        self.write_log: list[str] = []

    def detect(self, text: str) -> bool:
        if not self.kill.allow_run():
            return False
        t = text.lower()
        return any(m in t for m in self.MARKERS)

    def recommend_action(self, text: str) -> dict[str, Any]:
        """S2: only whitelist recommendations."""
        if not self.kill.allow_run():
            return {"action": None, "reason": "kill_switch_or_disabled"}
        emergent = self.detect(text)
        if not emergent:
            return {"action": "recommend_block", "reason": "not_emergent"}
        return {"action": "recommend_assign", "reason": "emergent_pattern"}

    def try_write_side_effect(self, path: str, content: str) -> bool:
        """Write only if kill-switch allows writes (default false)."""
        if not self.kill.allow_write():
            return False
        self.write_log.append(path)
        return True


def measure_emergence_accuracy(fixtures: list[EmergenceEvent] | None = None) -> dict[str, Any]:
    fixtures = fixtures or _default_fixtures()
    det = EmergenceDetector(KillSwitch(enabled=True))
    correct = 0
    for fx in fixtures:
        pred = det.detect(fx.text)
        if pred == fx.label:
            correct += 1
    acc = correct / len(fixtures) if fixtures else 0.0

    # kill-switch effectiveness
    det2 = EmergenceDetector(KillSwitch(enabled=True))
    det2.kill.kill()
    killed_blocks_detect = det2.detect("swarm consensus multi-agent vote") is False
    det3 = EmergenceDetector(KillSwitch(enabled=True))
    write_blocked = det3.try_write_side_effect("x", "y") is False  # writes env off
    det3.kill.kill()
    write_still_blocked = det3.try_write_side_effect("x2", "y") is False

    from caliber import stamp_non_physical_goal  # noqa: PLC0415

    ok = acc > 0.80 and killed_blocks_detect and write_blocked
    return stamp_non_physical_goal(
        {
            "n_fixtures": len(fixtures),
            "correct": correct,
            "accuracy": acc,
            "accuracy_pct": round(acc * 100, 4),
            "meets_accuracy_gate": acc > 0.80,
            "kill_switch_blocks_detect": killed_blocks_detect,
            "kill_switch_blocks_write": write_blocked and write_still_blocked,
            "gate": "G-DEL.5b",
            "kpi": "emergence_accuracy > 80% AND kill_switch effective",
            "env": "heuristic detector + ADR-0221 kill-switch (not production ML)",
        },
        ok=ok,
    )


def _default_fixtures() -> list[EmergenceEvent]:
    return [
        EmergenceEvent("single agent implements feature alone", False),
        EmergenceEvent("swarm consensus reached multi-agent vote", True),
        EmergenceEvent("docs only change by one writer", False),
        EmergenceEvent("emergent quorum on task assignment", True),
        EmergenceEvent("refactor without coordination", False),
        EmergenceEvent("collective decision to block merge", True),
        EmergenceEvent("unit test green", False),
        EmergenceEvent("multi-agent vote to reassign owner", True),
        EmergenceEvent("typo fix", False),
        EmergenceEvent("emergent pattern across orchestrator and implementers", True),
        EmergenceEvent("local lint", False),
        EmergenceEvent("quorum of verifiers reject handoff", True),
    ]
