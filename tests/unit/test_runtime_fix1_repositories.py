from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from omlxc import storage
from omlxc.storage import SQLiteRuntimeStore


@pytest.mark.asyncio
async def test_route_audit_and_config_revision_round_trip_pagination_and_restart(
    tmp_path: Path,
) -> None:
    RouteAuditWrite = storage.RouteAuditWrite
    ConfigRevisionWrite = storage.ConfigRevisionWrite
    database = tmp_path / "state.db"
    store = await SQLiteRuntimeStore.open(database)
    now = datetime(2026, 8, 11, 12, tzinfo=UTC)
    suspicious = "req'; DROP TABLE route_audits; --"
    first = await store.append_route_audit(
        RouteAuditWrite(
            request_id=suspicious,
            observed_at=now,
            selected_placement_id=None,
            candidates=("placement-a",),
            rejections={"placement-a": "capacity"},
            config_revision="config-1",
        )
    )
    second = await store.append_route_audit(
        RouteAuditWrite(
            request_id="req-2",
            observed_at=now + timedelta(seconds=1),
            selected_placement_id="placement-b",
            candidates=("placement-b",),
            rejections={},
            config_revision="config-2",
        )
    )
    config_one = await store.save_config_revision(
        ConfigRevisionWrite(
            revision_id="config-1",
            observed_at=now,
            rollback_reference="snapshot:config-0",
            config_json='{"z":2,"enabled":true}',
            fingerprint="sha256:" + "a" * 64,
        )
    )
    config_two = await store.save_config_revision(
        ConfigRevisionWrite(
            revision_id="config-2",
            observed_at=now + timedelta(seconds=1),
            rollback_reference="snapshot:config-1",
            config_json='{"enabled":false}',
            fingerprint="sha256:" + "b" * 64,
        )
    )
    assert first.sequence < second.sequence
    assert config_one.sequence < config_two.sequence
    await store.close()

    reopened = await SQLiteRuntimeStore.open(database)
    page_one = await reopened.list_route_audits(after_sequence=0, limit=1)
    page_two = await reopened.list_route_audits(after_sequence=page_one[-1].sequence, limit=1)
    assert page_one[0].request_id == suspicious
    assert page_two[0].request_id == "req-2"
    assert dict(page_one[0].rejections) == {"placement-a": "capacity"}
    assert await reopened.latest_config_revision() == config_two
    assert config_one.config_json == '{"enabled":true,"z":2}'
    assert await reopened.list_config_revisions(after_sequence=0, limit=10) == (
        config_one,
        config_two,
    )
    await reopened.close()


@pytest.mark.asyncio
async def test_route_and_config_repository_validation_fails_closed(tmp_path: Path) -> None:
    RouteAuditWrite = storage.RouteAuditWrite
    ConfigRevisionWrite = storage.ConfigRevisionWrite
    store = await SQLiteRuntimeStore.open(tmp_path / "state.db")
    now = datetime(2026, 8, 11, 12, tzinfo=UTC)
    with pytest.raises(ValueError, match="timezone"):
        await store.append_route_audit(
            RouteAuditWrite("req", datetime(2026, 8, 11), None, (), {}, "config-1")
        )
    with pytest.raises(ValueError, match="size"):
        await store.append_route_audit(
            RouteAuditWrite("req", now, None, (), {"x": "y" * (70 * 1024)}, "config-1")
        )
    with pytest.raises(ValueError, match="rollback"):
        await store.save_config_revision(
            ConfigRevisionWrite(
                revision_id="config-1",
                observed_at=now,
                rollback_reference="Authorization: Bearer secret",
                config_json="{}",
                fingerprint="sha256:" + "a" * 64,
            )
        )
    for invalid_json in ('["not-an-object"]', '{"value":NaN}', "not-json"):
        with pytest.raises(ValueError, match="config revision JSON"):
            await store.save_config_revision(
                ConfigRevisionWrite(
                    revision_id="config-invalid",
                    observed_at=now,
                    rollback_reference=None,
                    config_json=invalid_json,
                    fingerprint="sha256:" + "a" * 64,
                )
            )
    with pytest.raises(ValueError, match="size"):
        await store.save_config_revision(
            ConfigRevisionWrite(
                revision_id="config-large",
                observed_at=now,
                rollback_reference=None,
                config_json='{"value":"' + "x" * (70 * 1024) + '"}',
                fingerprint="sha256:" + "a" * 64,
            )
        )
    with pytest.raises(ValueError, match="page"):
        await store.list_route_audits(after_sequence=0, limit=501)
    await store.close()
