from __future__ import annotations

import os
from pathlib import Path

import pytest

import omlxc.storage.database as database_module
from omlxc.storage import SQLiteRuntimeStore


def _write_asset(path: Path, payload: bytes) -> None:
    path.write_bytes(payload)
    os.chmod(path, 0o666)


@pytest.mark.asyncio
async def test_corrupt_wal_asset_group_moves_to_private_quarantine(tmp_path: Path) -> None:
    primary = tmp_path / "state.db"
    assets = {
        "state.db": b"bad primary",
        "state.db-wal": b"valuable wal",
        "state.db-shm": b"valuable shm",
    }
    for name, payload in assets.items():
        _write_asset(tmp_path / name, payload)

    store = await SQLiteRuntimeStore.open(primary, quarantine_suffix_factory=lambda: "asset-group")
    try:
        assert store.degraded
        quarantine = tmp_path / "state.db.corrupt-asset-group"
        assert quarantine.is_dir()
        assert quarantine.stat().st_mode & 0o077 == 0
        for name, payload in assets.items():
            quarantined = quarantine / name
            assert quarantined.read_bytes() == payload
            assert quarantined.stat().st_mode & 0o077 == 0
            assert not (tmp_path / name).exists()
        assert not (tmp_path / "state.db.quarantine-in-progress").exists()
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_quarantine_fsyncs_private_directory_and_parent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    primary = tmp_path / "state.db"
    _write_asset(primary, b"bad primary")
    fsynced: list[Path] = []
    monkeypatch.setattr(
        database_module, "_fsync_path", lambda path: fsynced.append(path), raising=False
    )
    store = await SQLiteRuntimeStore.open(primary, quarantine_suffix_factory=lambda: "fsync")
    try:
        assert store.degraded
        assert fsynced[-2:] == [tmp_path / "state.db.corrupt-fsync", tmp_path]
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_orphan_sidecar_starts_quarantine_instead_of_fake_primary(tmp_path: Path) -> None:
    primary = tmp_path / "state.db"
    _write_asset(tmp_path / "state.db-wal", b"orphan only")
    store = await SQLiteRuntimeStore.open(primary, quarantine_suffix_factory=lambda: "orphan")
    try:
        assert store.degraded
        assert not primary.exists()
        assert (
            tmp_path / "state.db.corrupt-orphan" / "state.db-wal"
        ).read_bytes() == b"orphan only"
    finally:
        await store.close()
