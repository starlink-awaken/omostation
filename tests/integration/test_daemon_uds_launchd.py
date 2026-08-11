from __future__ import annotations

import json
import os
import plistlib
import socket
import stat
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest
from typer.testing import CliRunner

from omlxc.api import create_app
from omlxc.daemon import DaemonServer
from omlxc.daemon import app as daemon_cli
from omlxc.events import EventPriority, EventSubscriptionClosed, RuntimeEvent
from omlxc.service import LaunchdPaths, build_launchd_plan, write_launchd_plist
from omlxc.storage import DurableEventRecord


class HealthControl:
    async def health(self) -> dict[str, Any]:
        return {"status": "ready", "degraded": False}


class OneEventSubscription:
    def __init__(self, event: RuntimeEvent) -> None:
        self._event = event
        self._sent = False
        self.closed = False

    async def receive(self) -> RuntimeEvent:
        if self._sent:
            raise EventSubscriptionClosed("complete")
        self._sent = True
        return self._event

    async def close(self) -> None:
        self.closed = True


class FakeEvents:
    def __init__(self) -> None:
        now = datetime(2026, 8, 11, tzinfo=UTC)
        self.subscription = OneEventSubscription(
            RuntimeEvent.create(
                event_id="live-2",
                priority=EventPriority.HIGH,
                kind="job.running",
                timestamp=now,
                payload={"state": "running"},
                job_id="job-1",
            )
        )
        self.replayed_after: list[int] = []
        self.record = DurableEventRecord(
            sequence=1,
            event_id="durable-1",
            schema_version=1,
            observed_at=now,
            priority="high",
            kind="job.pending",
            payload_json='{"state":"pending"}',
            job_id="job-1",
            resource_id=None,
        )

    async def replay_events(
        self, *, after_sequence: int, limit: int
    ) -> tuple[DurableEventRecord, ...]:
        self.replayed_after.append(after_sequence)
        return (self.record,) if after_sequence < 1 else ()

    def subscribe_events(self) -> OneEventSubscription:
        return self.subscription


@pytest.mark.asyncio
async def test_events_replay_then_live_ndjson_and_close_subscription() -> None:
    events = FakeEvents()
    transport = httpx.ASGITransport(app=create_app(events=events))
    async with httpx.AsyncClient(transport=transport, base_url="http://omlxc") as client:
        response = await client.get("/api/v1/events?after=0")

    lines = [json.loads(line) for line in response.text.splitlines()]
    assert [line["event_id"] for line in lines] == ["durable-1", "live-2"]
    assert lines[0]["cursor"] == 1
    assert lines[1]["priority"] == "high"
    assert events.replayed_after == [0, 1]
    assert events.subscription.closed


@pytest.mark.asyncio
async def test_real_tmp_uds_permissions_concurrency_and_restart() -> None:
    with tempfile.TemporaryDirectory(prefix="omlxc-", dir="/tmp") as directory:
        socket_path = Path(directory) / "private/omlxcd.sock"
        server = DaemonServer(create_app(control=HealthControl()), socket_path=socket_path)
        await server.start()
        try:
            assert stat.S_IMODE(socket_path.parent.stat().st_mode) == 0o700
            assert stat.S_ISSOCK(socket_path.stat().st_mode)
            assert stat.S_IMODE(socket_path.stat().st_mode) == 0o600
            transport = httpx.AsyncHTTPTransport(uds=str(socket_path))
            async with httpx.AsyncClient(transport=transport, base_url="http://omlxc") as client:
                responses = [await client.get("/api/v1/health") for _ in range(4)]
            assert all(response.status_code == 200 for response in responses)

            contender = DaemonServer(create_app(control=HealthControl()), socket_path=socket_path)
            with pytest.raises(RuntimeError, match="active Unix socket"):
                await contender.start()
        finally:
            await server.stop()

        assert not socket_path.exists()
        await server.start()
        try:
            transport = httpx.AsyncHTTPTransport(uds=str(socket_path))
            async with httpx.AsyncClient(transport=transport, base_url="http://omlxc") as client:
                assert (await client.get("/api/v1/health")).status_code == 200
        finally:
            await server.stop()
        assert server.task_settled


@pytest.mark.asyncio
async def test_uds_rejects_symlink_regular_file_and_foreign_listener() -> None:
    with tempfile.TemporaryDirectory(prefix="omlxc-", dir="/tmp") as directory:
        tmp_path = Path(directory)
        regular = tmp_path / "regular.sock"
        regular.write_text("do not replace", encoding="utf-8")
        with pytest.raises(RuntimeError, match="non-socket"):
            await DaemonServer(create_app(), socket_path=regular).start()
        assert regular.read_text(encoding="utf-8") == "do not replace"

        target = tmp_path / "target"
        target.write_text("target", encoding="utf-8")
        link = tmp_path / "link.sock"
        link.symlink_to(target)
        with pytest.raises(RuntimeError, match="symlink"):
            await DaemonServer(create_app(), socket_path=link).start()
        assert link.is_symlink()

        active = tmp_path / "active.sock"
        listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        listener.bind(str(active))
        listener.listen(1)
        try:
            with pytest.raises(RuntimeError, match="active Unix socket"):
                await DaemonServer(create_app(), socket_path=active).start()
        finally:
            listener.close()
            active.unlink()


def test_launchd_plist_is_pure_private_and_contains_no_secret(tmp_path: Path) -> None:
    home = tmp_path / "home"
    paths = LaunchdPaths.for_home(home)
    plan = build_launchd_plan(paths)
    payload = plistlib.loads(plan.plist_bytes)

    assert payload["Label"] == "com.omlxc.daemon"
    assert payload["ProgramArguments"][0] == str(home / ".local/bin/omlxcd")
    assert payload["RunAtLoad"] is True
    assert payload["KeepAlive"] is True
    assert "uv" not in " ".join(payload["ProgramArguments"])
    encoded = plan.plist_bytes.lower()
    assert b"token" not in encoded and b"secret" not in encoded and b"api_key" not in encoded

    first = write_launchd_plist(plan)
    assert first.path == paths.plist_path
    assert first.snapshot_path is None
    old_payload = first.path.read_bytes()
    second = write_launchd_plist(plan)
    assert second.snapshot_path is not None
    assert second.snapshot_path.read_bytes() == old_payload
    assert stat.S_IMODE(second.snapshot_path.stat().st_mode) == 0o600
    assert stat.S_IMODE(second.path.stat().st_mode) == 0o600
    assert stat.S_IMODE(second.path.parent.stat().st_mode) == 0o700
    assert plistlib.loads(second.path.read_bytes()) == payload
    assert plan.uninstall_preserves == (paths.log_directory, paths.data_directory)


def test_daemon_entry_help_and_bad_config_do_not_echo_secrets(tmp_path: Path) -> None:
    runner = CliRunner()
    help_result = runner.invoke(daemon_cli, ["--help"])
    assert help_result.exit_code == 0
    assert "Unix Socket" in help_result.stdout

    config = tmp_path / "bad.toml"
    config.write_text('api_key = "do-not-echo"\n', encoding="utf-8")
    result = runner.invoke(daemon_cli, ["--config", str(config), "--check"])
    assert result.exit_code == 2
    assert "do-not-echo" not in result.stdout + (result.stderr or "")
    assert os.path.exists(config)
