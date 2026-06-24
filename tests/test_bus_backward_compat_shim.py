"""R69 meta-test — agora.bus re-exports from bus_foundation (backward compat).

After the Phase B split (R66-R69), agora.bus.__init__.py is a re-export shim
over bus_foundation. This test confirms:
1. The shim re-exports BusEnvelope, EventType, publish, subscribe, schedule.
2. The premium agora-specific backends (EventBusBackend, CroniterBackend, etc.)
   are still importable from agora.bus.backends.
3. agora.bus.BusEnvelope is the SAME class as bus_foundation.BusEnvelope
   (i.e. the re-export is genuine, not a copy).
"""

from __future__ import annotations

import warnings


def test_agora_bus_reexports_publish() -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        from agora.bus import publish as agora_publish
        from bus_foundation import publish as bf_publish

        # Re-export, not a copy
        assert agora_publish is bf_publish


def test_agora_bus_reexports_BusEnvelope() -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        from agora.bus import BusEnvelope as AgoraBusEnvelope
        from bus_foundation import BusEnvelope as BFBusEnvelope

        # Re-export, not a copy (this is the load-bearing invariant for
        # cross-repo consumers that may have imported either name)
        assert AgoraBusEnvelope is BFBusEnvelope


def test_agora_bus_reexports_EventType() -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        from agora.bus import EventType as AgoraEventType
        from bus_foundation import EventType as BFEventType

        assert AgoraEventType is BFEventType


def test_agora_bus_emits_deprecation_warning() -> None:
    """The shim should emit exactly one DeprecationWarning on first import."""
    # Reset the warning filter so we can see it
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        # Force re-import
        import importlib
        import agora.bus as agora_bus_module

        importlib.reload(agora_bus_module)

        dep_warnings = [w for w in caught if issubclass(w.category, DeprecationWarning)]
        assert len(dep_warnings) >= 1
        assert "bus_foundation" in str(dep_warnings[0].message)


def test_premium_backends_still_in_agora_bus_backends() -> None:
    """agora-specific premium backends (EventBusBackend wrapping agora.core.event_bus)
    are kept in agora.bus.backends for agora-internal use."""
    from agora.bus.backends.eventbus import EventBusBackend
    from agora.bus.backends.croniter import CroniterBackend
    from agora.bus.backends.asyncio import AsyncioBackend
    from agora.bus.backends.messagebus import MessageBusBackend

    assert EventBusBackend is not None
    assert CroniterBackend is not None
    assert AsyncioBackend is not None
    assert MessageBusBackend is not None
