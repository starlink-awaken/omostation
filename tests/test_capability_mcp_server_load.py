"""T1-12 (WP-T1-12-P0-EXACT-MCP-LOAD) — shared capability find/load helper contract.

The helper is the single read-only boundary over bin/capability-sync.py:
exact ids only, fail-closed on miss/invalid, no execution, no admission.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_HELPER_PATH = ROOT / "lib" / "capability_mcp_server_load.py"

import importlib.util

_spec = importlib.util.spec_from_file_location(
    "capability_mcp_server_load_test", _HELPER_PATH
)
assert _spec is not None and _spec.loader is not None
_mod = importlib.util.module_from_spec(_spec)
sys.modules["capability_mcp_server_load_test"] = _mod
_spec.loader.exec_module(_mod)

CapabilityLoadError = _mod.CapabilityLoadError
find_capability = _mod.find_capability
inspect_capability = _mod.inspect_capability
load_capability = _mod.load_capability
load_sync_module = _mod.load_sync_module


@pytest.fixture(scope="module")
def sync_module():
    return load_sync_module(ROOT)


RESOLVED_IDS = [
    "skill:git-discipline",
    "workflow:bet-execution",
    "mcp-server:agora",
]


@pytest.mark.parametrize("capability_id", RESOLVED_IDS)
def test_find_resolves_exact_ids(capability_id: str) -> None:
    receipt = find_capability(capability_id, root=ROOT)
    assert receipt["status"] == "resolved"
    assert receipt["match_count"] >= 1
    assert receipt["capability_id"] == capability_id
    assert receipt["schema"] == "capability-resolution-receipt/v1"


def test_find_miss_raises_capability_not_found() -> None:
    with pytest.raises(CapabilityLoadError, match="capability_not_found"):
        find_capability("skill:definitely-not-here-xyz", root=ROOT)


@pytest.mark.parametrize(
    "bad_id",
    [
        "git-discipline",  # no prefix
        "unknown:thing",  # unsupported prefix
        "",
        "skill:",  # empty tail
    ],
)
def test_find_rejects_non_exact_ids(bad_id: str) -> None:
    with pytest.raises(CapabilityLoadError, match="capability_id_invalid"):
        find_capability(bad_id, root=ROOT)


def test_inspect_returns_native_inspection_receipt() -> None:
    receipt = inspect_capability("skill:git-discipline", root=ROOT)
    assert receipt["schema"] == "native-capability-inspection-receipt/v1"
    assert receipt["status"] == "inspected"


def test_load_combines_resolution_and_inspection() -> None:
    payload = load_capability("workflow:bet-execution", root=ROOT)
    assert payload["capability_id"] == "workflow:bet-execution"
    assert payload["resolution"]["status"] == "resolved"
    assert payload["inspection"]["status"] == "inspected"


def test_resolver_module_is_cached() -> None:
    assert load_sync_module(ROOT) is load_sync_module(ROOT)
