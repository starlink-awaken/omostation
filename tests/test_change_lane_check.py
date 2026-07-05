"""Tests for change-lane-check.py classify + allowed_for (ADR-0129 §11.3.2).

Covers:
- .omo/state/runtime/ path recognition (ADR-0129 MVP canonical projection plane)
- allowed_for priority: workflow explicit auth overrides hardcoded runtime_snapshot isolation
"""
import importlib.util
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location(
    "change_lane_check", str(WORKSPACE / "bin" / "change-lane-check.py")
)
clc = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(clc)


def test_classify_state_runtime_health_yaml_is_runtime_snapshot():
    """ADR-0129 §5.4: .omo/state/runtime/ canonical projection plane → runtime_snapshot lane."""
    assert clc.classify(".omo/state/runtime/health.yaml", submodules=set()) == "runtime_snapshot"


def test_classify_state_runtime_brief_md_is_runtime_snapshot():
    """BRIEF.md moved to .omo/state/runtime/brief.md also runtime_snapshot."""
    assert clc.classify(".omo/state/runtime/brief.md", submodules=set()) == "runtime_snapshot"


def test_classify_legacy_state_health_still_governance_state():
    """Legacy .omo/state/health.yaml (not under runtime/) still governance_state."""
    assert clc.classify(".omo/state/health.yaml", submodules=set()) == "governance_state"


def test_allowed_for_workflow_auth_overrides_runtime_snapshot_isolation():
    """ADR-0129 §11.3.2: workflow 显式授权优先于硬编码 runtime_snapshot 隔离."""
    lanes = {"runtime_snapshot", "governance_state"}
    allowed = {"runtime_snapshot", "governance_state"}
    assert clc.allowed_for(lanes, allowed_lanes=allowed) is True


def test_runtime_snapshot_isolation_still_blocks_unauthorized_mix():
    """无 allowed_lanes 时, runtime_snapshot 仍不能与其他 lane 混."""
    lanes = {"runtime_snapshot", "governance_state"}
    assert clc.allowed_for(lanes, allowed_lanes=set()) is False


def test_allowed_for_single_lane_always_passes():
    """单 lane 永远 PASS."""
    assert clc.allowed_for({"runtime_snapshot"}, allowed_lanes=set()) is True
    assert clc.allowed_for({"governance_state"}, allowed_lanes=set()) is True
