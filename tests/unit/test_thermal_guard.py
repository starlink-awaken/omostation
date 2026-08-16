"""Unit tests for ThermalGuard and environmental health sensing."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from omlxc.dataplane.thermal import (
    NodeEnvironmentalState,
    PowerSource,
    ThermalGuard,
    ThermalPressureLevel,
)


def test_thermal_penalty_calculation() -> None:
    guard = ThermalGuard()

    # Nominal + AC -> 1.0
    assert guard.calculate_penalty(ThermalPressureLevel.NOMINAL, PowerSource.AC) == 1.0

    # Moderate thermal -> 0.7
    assert guard.calculate_penalty(ThermalPressureLevel.MODERATE, PowerSource.AC) == 0.7

    # Heavy thermal -> 0.5
    assert guard.calculate_penalty(ThermalPressureLevel.HEAVY, PowerSource.AC) == 0.5

    # Trapping thermal -> 0.1
    assert guard.calculate_penalty(ThermalPressureLevel.TRAPPING, PowerSource.AC) == 0.1

    # Battery power with healthy charge (>50%) -> 0.7
    assert guard.calculate_penalty(ThermalPressureLevel.NOMINAL, PowerSource.BATTERY, 85.0) == 0.7

    # Battery power with moderate charge (<50%) -> 0.5
    assert guard.calculate_penalty(ThermalPressureLevel.NOMINAL, PowerSource.BATTERY, 45.0) == 0.5

    # Battery power with critical charge (<15%) -> 0.1
    assert guard.calculate_penalty(ThermalPressureLevel.NOMINAL, PowerSource.BATTERY, 10.0) == 0.1


def test_thermal_guard_cache_ttl() -> None:
    guard = ThermalGuard(cache_ttl_seconds=10.0)
    fake_state = NodeEnvironmentalState(
        thermal_level=ThermalPressureLevel.NOMINAL,
        power_source=PowerSource.AC,
        battery_percent=None,
        penalty_multiplier=1.0,
        recorded_at=100.0,
    )
    guard._cached_state = fake_state

    # Query within TTL
    probed = guard.probe(now=105.0)
    assert probed == fake_state

    # Query after TTL expires
    mock_ret = (ThermalPressureLevel.HEAVY, PowerSource.AC, None)
    with patch.object(guard, "_probe_os", return_value=mock_ret):
        probed_new = guard.probe(now=115.0)
        assert probed_new.thermal_level == ThermalPressureLevel.HEAVY
        assert probed_new.penalty_multiplier == 0.5


def test_probe_darwin_parsing() -> None:
    guard = ThermalGuard()

    with patch("shutil.which", return_value="/usr/bin/pmset"):
        therm_mock = MagicMock(
            returncode=0, stdout="Note: Thermal pressure level: Moderate\n"
        )
        batt_mock = MagicMock(
            returncode=0, stdout="Now drawing from 'Battery Power'\n -InternalBattery-0 65%\n"
        )

        with patch("subprocess.run", side_effect=[therm_mock, batt_mock]):
            therm, power, batt = guard._probe_darwin()
            assert therm == ThermalPressureLevel.MODERATE
            assert power == PowerSource.BATTERY
            assert batt == 65.0


def test_remote_node_state_updates() -> None:
    guard = ThermalGuard(cache_ttl_seconds=5.0)

    # Remote node reports Heavy thermal
    guard.update_node_state(
        node_id="y7000p-rtx4070",
        thermal_level=ThermalPressureLevel.HEAVY,
        power_source=PowerSource.AC,
        now=100.0,
    )

    state = guard.get_node_state("y7000p-rtx4070", is_local=False, now=110.0)
    assert state.thermal_level == ThermalPressureLevel.HEAVY
    assert state.penalty_multiplier == 0.5

    # Remote node heartbeat expires (>60s) -> defaults to Nominal
    state_expired = guard.get_node_state("y7000p-rtx4070", is_local=False, now=180.0)
    assert state_expired.thermal_level == ThermalPressureLevel.NOMINAL
    assert state_expired.penalty_multiplier == 1.0
