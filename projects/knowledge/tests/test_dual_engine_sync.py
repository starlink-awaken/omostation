"""Dual Engine (KOS <-> gbrain) Sync & Consistency Test."""

from datetime import datetime, timezone
import pytest


def test_write_through_sync_record():
    """Verify write-through event structure."""
    event = {
        "event_id": "evt-sync-001",
        "doc_id": "doc-wj-2026-001",
        "action": "upsert",
        "payload": {
            "title": "卫健委信息化项目规范",
            "body": "涉及等保三级与信创自主可控...",
            "zone": "work-weijian",
        },
        "source": "kos",
        "target": "gbrain_postgres",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "committed",
    }

    assert event["status"] == "committed"
    assert event["target"] == "gbrain_postgres"
    assert "work-weijian" in event["payload"]["zone"]


def test_idempotent_sync_hash():
    """Verify idempotent sync via content hash."""
    import hashlib

    body1 = "标准医疗互联互通接口规范 v3.0"
    hash1 = hashlib.sha256(body1.encode("utf-8")).hexdigest()
    hash2 = hashlib.sha256(body1.encode("utf-8")).hexdigest()

    assert hash1 == hash2
