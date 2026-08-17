"""
Hardware thermal pressure and power supply state probe for omlxc.

Observes node environmental health (macOS pmset / Linux sysfs / fallback)
and provides score penalty multipliers to protect laptops from thermal throttling
and battery exhaustion.
"""

from __future__ import annotations

import enum
import logging
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import Final

logger = logging.getLogger(__name__)


class ThermalPressureLevel(enum.StrEnum):
    """macOS / OS thermal pressure levels."""

    NOMINAL = "nominal"
    MODERATE = "moderate"
    HEAVY = "heavy"
    TRAPPING = "trapping"
    UNKNOWN = "unknown"


class PowerSource(enum.StrEnum):
    """System power supply status."""

    AC = "ac"
    BATTERY = "battery"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class NodeEnvironmentalState:
    """Snapshot of hardware thermal and power metrics."""

    thermal_level: ThermalPressureLevel = ThermalPressureLevel.NOMINAL
    power_source: PowerSource = PowerSource.AC
    battery_percent: float | None = None
    penalty_multiplier: float = 1.0
    recorded_at: float = 0.0


DEFAULT_CACHE_TTL_SECONDS: Final[float] = 5.0


class ThermalGuard:
    """Probes host hardware environment and computes routing penalties."""

    def __init__(self, cache_ttl_seconds: float = DEFAULT_CACHE_TTL_SECONDS) -> None:
        self._cache_ttl_seconds = cache_ttl_seconds
        self._cached_state: NodeEnvironmentalState | None = None
        self._remote_states: dict[str, NodeEnvironmentalState] = {}

    def update_node_state(
        self,
        node_id: str,
        thermal_level: ThermalPressureLevel,
        power_source: PowerSource = PowerSource.AC,
        battery_percent: float | None = None,
        now: float | None = None,
    ) -> NodeEnvironmentalState:
        """Register or update an environmental telemetry report for a remote cluster node."""
        current_time = time.monotonic() if now is None else now
        penalty = self.calculate_penalty(thermal_level, power_source, battery_percent)
        state = NodeEnvironmentalState(
            thermal_level=thermal_level,
            power_source=power_source,
            battery_percent=battery_percent,
            penalty_multiplier=penalty,
            recorded_at=current_time,
        )
        self._remote_states[node_id] = state
        return state

    def get_node_state(
        self, node_id: str, *, is_local: bool = True, now: float | None = None
    ) -> NodeEnvironmentalState:
        """Fetch environmental state for a specific local or remote node."""
        if is_local:
            return self.probe(now=now)
        if node_id in self._remote_states:
            state = self._remote_states[node_id]
            current_time = time.monotonic() if now is None else now
            # Remote reports remain valid for up to 60 seconds
            if (current_time - state.recorded_at) < (self._cache_ttl_seconds * 12.0):
                return state
        return NodeEnvironmentalState(
            thermal_level=ThermalPressureLevel.NOMINAL,
            power_source=PowerSource.AC,
            battery_percent=None,
            penalty_multiplier=1.0,
            recorded_at=time.monotonic() if now is None else now,
        )

    def calculate_penalty(
        self,
        thermal_level: ThermalPressureLevel,
        power_source: PowerSource,
        battery_percent: float | None = None,
    ) -> float:
        """Compute score multiplier according to thermal and power conditions."""
        if thermal_level == ThermalPressureLevel.TRAPPING or (
            power_source == PowerSource.BATTERY and battery_percent is not None and battery_percent < 15.0
        ):
            return 0.1
        if thermal_level == ThermalPressureLevel.HEAVY or (
            power_source == PowerSource.BATTERY and battery_percent is not None and battery_percent < 50.0
        ):
            return 0.5
        if thermal_level == ThermalPressureLevel.MODERATE or power_source == PowerSource.BATTERY:
            return 0.7
        return 1.0

    def probe(self, now: float | None = None) -> NodeEnvironmentalState:
        """Fetch current hardware environmental snapshot (cached if recent)."""
        current_time = time.monotonic() if now is None else now
        if self._cached_state is not None and (current_time - self._cached_state.recorded_at) < self._cache_ttl_seconds:
            return self._cached_state

        thermal_level, power_source, battery_percent = self._probe_os()
        penalty = self.calculate_penalty(thermal_level, power_source, battery_percent)
        state = NodeEnvironmentalState(
            thermal_level=thermal_level,
            power_source=power_source,
            battery_percent=battery_percent,
            penalty_multiplier=penalty,
            recorded_at=current_time,
        )
        self._cached_state = state
        return state

    def _probe_os(self) -> tuple[ThermalPressureLevel, PowerSource, float | None]:
        """Probe underlying operating system."""
        if sys.platform == "darwin":
            return self._probe_darwin()
        return (ThermalPressureLevel.NOMINAL, PowerSource.AC, None)

    def _probe_darwin(self) -> tuple[ThermalPressureLevel, PowerSource, float | None]:
        """Parse macOS pmset commands."""
        pmset_bin = shutil.which("pmset")
        if not pmset_bin:
            return (ThermalPressureLevel.NOMINAL, PowerSource.AC, None)

        thermal_level = ThermalPressureLevel.NOMINAL
        power_source = PowerSource.AC
        battery_percent: float | None = None

        try:
            # Probe thermal
            therm_res = subprocess.run(
                [pmset_bin, "-g", "therm"],
                capture_output=True,
                text=True,
                timeout=1.0,
                check=False,
            )
            if therm_res.returncode == 0:
                out = therm_res.stdout.lower()
                if "trapping" in out:
                    thermal_level = ThermalPressureLevel.TRAPPING
                elif "heavy" in out:
                    thermal_level = ThermalPressureLevel.HEAVY
                elif "moderate" in out:
                    thermal_level = ThermalPressureLevel.MODERATE
                elif "nominal" in out:
                    thermal_level = ThermalPressureLevel.NOMINAL

            # Probe battery / power
            batt_res = subprocess.run(
                [pmset_bin, "-g", "batt"],
                capture_output=True,
                text=True,
                timeout=1.0,
                check=False,
            )
            if batt_res.returncode == 0:
                out = batt_res.stdout
                if "Battery Power" in out:
                    power_source = PowerSource.BATTERY
                elif "AC Power" in out:
                    power_source = PowerSource.AC

                match = re.search(r"(\d+)%", out)
                if match:
                    battery_percent = float(match.group(1))

        except Exception as exc:
            logger.debug("ThermalGuard probe non-fatal exception: %s", exc)

        return (thermal_level, power_source, battery_percent)
