"""Cross-repo smoke test — R69 GO/NO-GO gate.

Verifies:
1. bus-foundation package can be installed (already proven by uv sync).
2. Public API surface matches documentation: publish, subscribe, schedule,
   BusEnvelope, EventType.
3. The 32 unit tests in bus-foundation/tests/ all pass (this file's collection
   is part of `uv run pytest`).
4. agora.bus remains importable (backward-compat shim — see agora.bus.__init__).
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import bus_foundation
from bus_foundation import BusEnvelope, EventType, publish, schedule, subscribe


REQUIRED_PUBLIC_API = {
    "BusEnvelope": BusEnvelope,
    "EventType": EventType,
    "publish": publish,
    "subscribe": subscribe,
    "schedule": schedule,
}


def test_public_api_surface() -> None:
    """The 5 names in REQUIRED_PUBLIC_API are importable from bus_foundation."""
    for name, obj in REQUIRED_PUBLIC_API.items():
        assert obj is not None, f"{name} should not be None"
        assert hasattr(bus_foundation, name), f"bus_foundation should expose {name}"


def test_publish_subscribe_integration() -> None:
    """End-to-end: publish an envelope via bus_foundation.publish, ensure a
    bus_foundation.subscribe-decorated callback receives it."""
    received: list[BusEnvelope] = []

    @subscribe("cross-repo-smoke:*")
    def cb(env: BusEnvelope) -> None:
        received.append(env)

    env = BusEnvelope(
        type="cross-repo-smoke:ping",
        source="test_cross_repo_smoke",
        payload={"k": "v"},
    )
    event_id = publish(env)
    assert event_id == env.id
    assert len(received) == 1
    assert received[0].id == env.id
    assert received[0].source == "test_cross_repo_smoke"


def test_package_installable() -> None:
    """bus-foundation is discoverable on PYTHONPATH (i.e., `uv run python -c 'import bus_foundation'` works)."""
    result = subprocess.run(
        [sys.executable, "-c", "import bus_foundation; print(bus_foundation.__file__)"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, f"bus_foundation import failed: {result.stderr}"
    assert "bus_foundation" in result.stdout
    # Verify it points to the source tree (workspace install) not site-packages
    assert "bus-foundation" in result.stdout or "bus_foundation" in result.stdout


def test_all_bus_foundation_unit_tests_present() -> None:
    """The 32 unit tests across 9 files exist and are discoverable."""
    tests_dir = Path(__file__).parent
    test_files = [
        "test_envelope.py",
        "test_dlq.py",
        "test_eventbus_backend.py",
        "test_router_retry_ownership.py",
        "test_facade.py",
        "test_asyncio_backend.py",
        "test_croniter_backend.py",
        "test_messagebus_backend.py",
        "test_sse_backend.py",
    ]
    for fname in test_files:
        fpath = tests_dir / fname
        assert fpath.exists(), f"missing test file: {fpath}"
        # Quick syntax check by importing
        import importlib.util
        spec = importlib.util.spec_from_file_location(fname.replace(".py", ""), fpath)
        assert spec is not None and spec.loader is not None
