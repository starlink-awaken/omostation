"""Tests for AuditSubscriber identity-aware classification."""

from __future__ import annotations

import tempfile
import time
from pathlib import Path

from agora.audit_subscriber import AuditSubscriber
from agora.core.event_bus import EventBus
from agora.core.registry import ServiceRegistry


def test_on_event_uses_identity_payload_as_actor():
    registry = ServiceRegistry(storage_path=str(Path(tempfile.mkdtemp()) / "test-services.json"))
    bus = EventBus(registry=registry, storage_path=str(Path(tempfile.mkdtemp()) / "test-events.json"))
    subscriber = AuditSubscriber(bus, db_path=str(Path(tempfile.mkdtemp()) / "test-audit.db"))

    subscriber.on_event(
        {
            "id": "evt_identity",
            "time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "source": "agora-router",
            "type": "route:call.succeeded",
            "trace_id": "",
            "payload": {
                "tool": "minerva.research",
                "service": "minerva",
                "identity": {
                    "subject_id": "alice",
                    "subject_type": "user",
                    "issuer": "auth0",
                    "tenant": "acme",
                },
            },
        }
    )

    rows = subscriber.query(event_type="route:call.succeeded")
    assert len(rows) == 1
    assert rows[0]["actor"] == "user:alice"
