"""Autonomy Ladder — L0→L3 data-driven promotion/demotion (BET-Y1Q4-T3-01).

Hard gate criteria:
  L0 → L1: >= 20 observations
  L1 → L2: calibration >= 0.6 AND >= 30 consecutive accepted
  L2 → L3: calibration >= 0.85 AND >= 100 consecutive accepted
  Any → L0: single rejected verdict triggers demotion

Each level change emits an OMO event (autonomy.level_change).

Registry: .omo/_truth/registry/autonomy-levels.yaml
"""

from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

AUTONOMY_LEVELS = ("L0", "L1", "L2", "L3")

PROMOTION_CRITERIA: dict[str, dict[str, Any]] = {
    "L0": {"min_observations": 20},
    "L1": {"min_calibration": 0.6, "min_consecutive_accepted": 30},
    "L2": {"min_calibration": 0.85, "min_consecutive_accepted": 100},
}

# Drift monitoring (BET-Y2Q3-T3-02)
DRIFT_CONFIG: dict[str, Any] = {
    "window_size": 50,  # sliding window for recent performance
    "demotion_thresholds": {
        "L3": 0.75,  # if windowed cal < 0.75 at L3, demote to L2
        "L2": 0.50,  # if windowed cal < 0.50 at L2, demote to L1
        "L1": 0.40,  # if windowed cal < 0.40 at L1, demote to L0
    },
    "human_review_required_after_demotion": True,
}

REGISTRY_PATH = (
    Path(__file__).resolve().parent.parent.parent.parent.parent
    / ".omo"
    / "_truth"
    / "registry"
    / "autonomy-levels.yaml"
)


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _load_registry(path: Path | None = None) -> dict[str, Any]:
    p = path or REGISTRY_PATH
    if not p.exists():
        return {"capabilities": {}}
    with p.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data


def _save_registry(data: dict[str, Any], path: Path | None = None) -> None:
    p = path or REGISTRY_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=True)


def _emit_event(capability: str, from_level: str, to_level: str, reason: str) -> None:
    """Emit an OMO event for the level change."""
    try:
        subprocess.run(
            [
                "omo",
                "event",
                "emit",
                "--type",
                "autonomy.level_change",
                "--source",
                "autonomy-ladder",
                "--payload",
                json.dumps(
                    {
                        "capability": capability,
                        "from_level": from_level,
                        "to_level": to_level,
                        "reason": reason,
                        "ts": _utc_now(),
                    },
                    ensure_ascii=False,
                ),
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except Exception:
        logger.debug("OMO event emit failed (non-fatal)")


@dataclass
class CapabilityAutonomy:
    """Per-capability autonomy state."""

    capability: str
    level: str = "L0"
    observations: int = 0
    total_accepted: int = 0
    consecutive_accepted: int = 0
    calibration: float = 0.0
    last_adjudication: str = ""
    updated_at: str = ""
    # Drift monitoring (BET-Y2Q3-T3-02)
    recent_verdicts: list[str] = field(default_factory=list)
    requires_human_review: bool = False

    @classmethod
    def from_dict(cls, cap: str, data: dict[str, Any]) -> CapabilityAutonomy:
        return cls(
            capability=cap,
            level=data.get("level", "L0"),
            observations=data.get("observations", 0),
            total_accepted=data.get("total_accepted", 0),
            consecutive_accepted=data.get("consecutive_accepted", 0),
            calibration=data.get("calibration", 0.0),
            last_adjudication=data.get("last_adjudication", ""),
            updated_at=data.get("updated_at", ""),
            recent_verdicts=data.get("recent_verdicts", []),
            requires_human_review=data.get("requires_human_review", False),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "level": self.level,
            "observations": self.observations,
            "total_accepted": self.total_accepted,
            "consecutive_accepted": self.consecutive_accepted,
            "calibration": round(self.calibration, 4),
            "last_adjudication": self.last_adjudication,
            "updated_at": self.updated_at,
            "recent_verdicts": self.recent_verdicts[-DRIFT_CONFIG["window_size"] :],
            "requires_human_review": self.requires_human_review,
        }

    def windowed_calibration(self) -> float:
        """Calculate calibration over recent window (BET-Y2Q3-T3-02)."""
        if not self.recent_verdicts:
            return self.calibration
        accepted = sum(1 for v in self.recent_verdicts if v == "accepted")
        return accepted / len(self.recent_verdicts) if self.recent_verdicts else 0.0


class AutonomyLadder:
    """Manages autonomy level promotion/demotion for capabilities."""

    def __init__(self, registry_path: Path | None = None) -> None:
        self._path = registry_path or REGISTRY_PATH
        self._data = _load_registry(self._path)

    def get(self, capability: str) -> CapabilityAutonomy:
        caps = self._data.get("capabilities", {})
        if capability in caps:
            return CapabilityAutonomy.from_dict(capability, caps[capability])
        return CapabilityAutonomy(capability=capability)

    def record_adjudication(self, capability: str, verdict: str) -> dict[str, Any]:
        """Record one adjudication and check promotion/demotion.

        Returns a dict with: level_changed, from_level, to_level, reason (if changed).
        """
        cap = self.get(capability)
        old_level = cap.level

        cap.observations += 1
        cap.last_adjudication = verdict
        cap.updated_at = _utc_now()

        # Track recent verdicts for sliding window (BET-Y2Q3-T3-02)
        cap.recent_verdicts.append(verdict)
        window_size = DRIFT_CONFIG["window_size"]
        if len(cap.recent_verdicts) > window_size:
            cap.recent_verdicts = cap.recent_verdicts[-window_size:]

        if verdict == "accepted":
            cap.total_accepted += 1
            cap.consecutive_accepted += 1
            cap.calibration = (
                cap.total_accepted / cap.observations if cap.observations else 0.0
            )
        elif verdict == "modified":
            cap.calibration = (
                cap.total_accepted / cap.observations if cap.observations else 0.0
            )
        elif verdict == "rejected":
            cap.consecutive_accepted = 0
            cap.calibration = (
                cap.total_accepted / cap.observations if cap.observations else 0.0
            )

        result: dict[str, Any] = {"level_changed": False}

        # Immediate demotion on rejected (existing logic)
        if verdict == "rejected" and cap.level != "L0":
            new_level = "L0"
            result = self._apply_change(
                cap, old_level, new_level, f"rejected verdict (was {old_level})"
            )
            # Set human review flag (BET-Y2Q3-T3-02)
            if DRIFT_CONFIG["human_review_required_after_demotion"]:
                cap.requires_human_review = True

        # No immediate demotion — check drift and promotion
        if not result.get("level_changed"):
            # Drift-based demotion (BET-Y2Q3-T3-02)
            if cap.level != "L0" and not cap.requires_human_review:
                drift_result = self._check_drift(cap)
                if drift_result:
                    result = drift_result
                    # Set human review flag after drift demotion
                    if DRIFT_CONFIG["human_review_required_after_demotion"]:
                        cap.requires_human_review = True

            # Promotion check (blocked if requires_human_review)
            if not result.get("level_changed") and not cap.requires_human_review:
                target = self._check_promotion(cap)
                if target and AUTONOMY_LEVELS.index(target) > AUTONOMY_LEVELS.index(
                    cap.level
                ):
                    result = self._apply_change(
                        cap,
                        cap.level,
                        target,
                        f"promotion criteria met from {cap.level}",
                    )

        self._save(cap)
        return result

    def _check_promotion(self, cap: CapabilityAutonomy) -> str | None:
        """Check if promotion criteria are met. Returns target level or None."""
        current_idx = AUTONOMY_LEVELS.index(cap.level)
        if current_idx >= len(AUTONOMY_LEVELS) - 1:
            return None

        next_level = AUTONOMY_LEVELS[current_idx + 1]
        criteria = PROMOTION_CRITERIA.get(cap.level, {})

        min_obs = criteria.get("min_observations", 0)
        if min_obs and cap.observations < min_obs:
            return None

        min_cal = criteria.get("min_calibration", 0.0)
        if min_cal and cap.calibration < min_cal:
            return None

        min_consec = criteria.get("min_consecutive_accepted", 0)
        if min_consec and cap.consecutive_accepted < min_consec:
            return None

        return next_level

    def _check_drift(self, cap: CapabilityAutonomy) -> dict[str, Any] | None:
        """Check for performance drift using sliding window (BET-Y2Q3-T3-02).

        Returns change result if drift detected, None otherwise.
        """
        if cap.level == "L0":
            return None

        # Need minimum window size to check drift
        min_window = min(20, DRIFT_CONFIG["window_size"])
        if len(cap.recent_verdicts) < min_window:
            return None

        windowed_cal = cap.windowed_calibration()
        threshold = DRIFT_CONFIG["demotion_thresholds"].get(cap.level)

        if threshold is None or windowed_cal >= threshold:
            return None

        # Drift detected — demote one level
        current_idx = AUTONOMY_LEVELS.index(cap.level)
        if current_idx <= 0:
            return None

        new_level = AUTONOMY_LEVELS[current_idx - 1]
        reason = f"drift detected: windowed_cal={windowed_cal:.3f} < threshold={threshold} (was {cap.level})"
        return self._apply_change(cap, cap.level, new_level, reason)

    def check_mof_drift(self) -> dict[str, Any] | None:
        """Run MOF drift check. If drifting, record a rejected adjudication for 'system.mof_sync'."""
        try:
            import subprocess

            workspace_root = Path(__file__).resolve().parent.parent.parent.parent.parent
            res = subprocess.run(
                ["uv", "run", "python3", "bin/mof/gen-mof-artifacts.py", "--json"],
                capture_output=True,
                text=True,
                timeout=15,
                cwd=str(workspace_root),
            )
            data = json.loads(res.stdout)
            if data.get("drifts", 0) > 0:
                logger.warning(f"MOF drift detected: {data.get('findings')}")
                return self.record_adjudication("system.mof_sync", "rejected")
            else:
                return self.record_adjudication("system.mof_sync", "accepted")
        except Exception as e:
            logger.error(f"MOF drift check failed: {e}")
            return None

    def clear_human_review(self, capability: str) -> dict[str, Any]:
        """Clear the requires_human_review flag after human review (BET-Y2Q3-T3-02).

        This allows the capability to be promoted again.
        """
        cap = self.get(capability)
        if not cap.requires_human_review:
            return {"cleared": False, "reason": "no human review required"}

        cap.requires_human_review = False
        self._save(cap)
        logger.info(f"Autonomy {capability}: human_review cleared")
        return {"cleared": True, "capability": capability}

    def _apply_change(
        self, cap: CapabilityAutonomy, from_level: str, to_level: str, reason: str
    ) -> dict[str, Any]:
        cap.level = to_level
        _emit_event(cap.capability, from_level, to_level, reason)
        logger.info(f"Autonomy {cap.capability}: {from_level} → {to_level} ({reason})")
        return {
            "level_changed": True,
            "from_level": from_level,
            "to_level": to_level,
            "reason": reason,
        }

    def _save(self, cap: CapabilityAutonomy) -> None:
        if "capabilities" not in self._data:
            self._data["capabilities"] = {}
        self._data["capabilities"][cap.capability] = cap.to_dict()
        _save_registry(self._data, self._path)

    def snapshot(self) -> dict[str, Any]:
        """Return current state of all capabilities."""
        result: dict[str, Any] = {}
        for cap_name, cap_data in self._data.get("capabilities", {}).items():
            result[cap_name] = CapabilityAutonomy.from_dict(
                cap_name, cap_data
            ).to_dict()
        return result
