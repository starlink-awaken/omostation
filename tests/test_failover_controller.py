"""Tests for omlxc.dataplane.failover (BET-Y1Q3-T10-119).

7 unit tests covering:
1. Initial state = DUAL_LINK
2. Single heartbeat loss → no transition
3. 3 consecutive losses → HEARTBEAT_LOSS
4. 6 losses → DEGRADED
5. Recovery from DEGRADED → DUAL_RECOVERED
6. Takeover: winner-takes-all with lease
7. Audit log atomic append + size-based rotation
"""
from __future__ import annotations

import datetime as dt
import importlib.util
import json
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from omlxc.dataplane.failover import HeartbeatSnapshot

import pytest

WS_ROOT = Path(__file__).resolve().parent.parent
FO_PATH = WS_ROOT / "projects" / "omlxc" / "src" / "omlxc" / "dataplane" / "failover.py"


def _load_failover():
    """Load failover module by exec'ing it (bypasses dataclass module issue)."""
    import types
    source = FO_PATH.read_text(encoding="utf-8")
    mod = types.ModuleType("failover_under_test")
    mod.__file__ = str(FO_PATH)
    sys.modules["failover_under_test"] = mod
    exec(compile(source, str(FO_PATH), "exec"), mod.__dict__)
    return mod


@pytest.fixture
def fo():
    """Load failover + temp workspace."""
    import tempfile
    with tempfile.TemporaryDirectory(prefix="t10-119-") as tmp:
        workspace = Path(tmp)
        workspace.mkdir(parents=True, exist_ok=True)
        mod = _load_failover()
        ctrl = mod.FailoverController(
            workspace_root=workspace,
            node_id="node-A",
            peer_node_id="node-B",
            heartbeat_loss_threshold=3,
        )
        yield mod, ctrl


def _snap(connected: bool, ts: dt.datetime | None = None) -> HeartbeatSnapshot:
    mod = _load_failover()
    return mod.HeartbeatSnapshot(
        is_connected=connected,
        link_speed_gbps=120.0 if connected else 0.0,
        avg_latency_ms=1.5 if connected else 999.0,
        timestamp_utc=(ts or dt.datetime.now(dt.UTC)).isoformat(),
    )


def test_initial_state_is_dual_link(fo):
    mod, ctrl = fo
    assert ctrl.current_state() == mod.FailoverState.DUAL_LINK
    assert ctrl.events() == []  # no events at init


def test_single_heartbeat_loss_no_transition(fo):
    mod, ctrl = fo
    ctrl.on_heartbeat(_snap(connected=False))
    # 1 loss: still DUAL_LINK (threshold=3)
    assert ctrl.current_state() == mod.FailoverState.DUAL_LINK
    assert len(ctrl.events()) == 0


def test_three_consecutive_losses_heartbeat_loss(fo):
    mod, ctrl = fo
    for _ in range(3):
        ctrl.on_heartbeat(_snap(connected=False))
    assert ctrl.current_state() == mod.FailoverState.HEARTBEAT_LOSS
    events = ctrl.events()
    assert len(events) == 1
    assert events[0].from_state == "dual_link"
    assert events[0].to_state == "heartbeat_loss"


def test_six_losses_full_degrade(fo):
    mod, ctrl = fo
    for _ in range(6):
        ctrl.on_heartbeat(_snap(connected=False))
    assert ctrl.current_state() == mod.FailoverState.DEGRADED


def test_recovery_from_degraded_to_dual_recovered(fo):
    mod, ctrl = fo
    for _ in range(6):
        ctrl.on_heartbeat(_snap(connected=False))
    assert ctrl.current_state() == mod.FailoverState.DEGRADED
    ctrl.on_heartbeat(_snap(connected=True))
    assert ctrl.current_state() == mod.FailoverState.DUAL_RECOVERED


def test_takeover_winner_takes_all_with_lease(fo):
    mod, ctrl = fo
    # First takeover: granted
    assert ctrl.request_takeover("req-1", actor="node-A") is True
    # Second takeover while lease valid: refused
    assert ctrl.request_takeover("req-2", actor="node-B") is False
    # Wait lease expire, then takeover granted
    ctrl.lease_duration_s = 0  # immediate expiry
    ctrl._lease = dt.datetime.now(dt.UTC) - dt.timedelta(seconds=1)
    assert ctrl.request_takeover("req-3", actor="node-B") is True


def test_audit_log_atomic_append_and_size_rotation(fo):
    mod, ctrl = fo
    # Trigger one event to create audit entry
    for _ in range(3):
        ctrl.on_heartbeat(_snap(connected=False))
    # Force rotation by writing >1MB
    audit_path = ctrl.audit_path
    assert audit_path.exists()
    with open(audit_path, "a") as f:
        f.write('{"x":"' + "A" * 1_200_000 + '"}\n')
    # trigger another append to invoke rotation
    ctrl._append_audit(mod.FailoverEvent(
        timestamp_utc=dt.datetime.now(dt.UTC).isoformat(),
        event_type="rotated", from_state="x", to_state="y", actor="test",
    ))
    # Verify at least one rotation file exists
    rotated = list(ctrl.audit_path.parent.glob("failover-audit.jsonl.*"))
    assert len(rotated) >= 1, "rotation should produce failover-audit.jsonl.1"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
