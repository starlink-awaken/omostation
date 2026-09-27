"""Claims observation sampler → corruption watchdog regression tests.

Loads the repo-canonical sampler asset (the source of the launchd-deployed
artifact) with ``SourceFileLoader`` — the same pattern other tests use for
``bin/**/assets/*.py.asset`` — and exercises the watchdog contract:
read-only detection, incident snapshot evidence, alert log, restore-source
digest validation, atomic restore and the cooldown rails.

The fixture plane is built through the production store constructor and the
production receipt/witness/high-water writers, so the assertions run against
the real chain verifier (incident 2026-09-26: raw-sqlite writes made the
official CLI UNAVAILABLE for ~6h).
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import sys
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta, timezone
from importlib.machinery import SourceFileLoader
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
ASSET = ROOT / "bin" / "claims-observation" / "sampler.py.asset"

sys.path.insert(0, str(ROOT / "projects/omo/src"))
from omo.workflow import claims_authority as ca  # noqa: E402

T0 = datetime(2026, 9, 27, 4, 0, 0, tzinfo=UTC)


@dataclass
class Env:
    module: object
    paths: ca.AuthorityPaths
    obs: Path
    receipt: dict


def _load_module():
    assert ASSET.is_file(), f"watchdog source missing: {ASSET}"
    loader = SourceFileLoader("claims_observation_sampler_watchdog_test", str(ASSET))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    loader.exec_module(module)
    return module


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _byte_flip(path: Path, needle: bytes) -> None:
    """Corrupt one byte inside a known text span (kimi-style raw write)."""
    data = path.read_bytes()
    index = data.index(needle) + len(needle) // 2
    flipped = bytearray(data)
    flipped[index] = flipped[index] + 1 if flipped[index] < 127 else flipped[index] - 1
    path.write_bytes(bytes(flipped))


def _build_plane(authority_dir: Path) -> tuple[ca.AuthorityPaths, ca._AuthorityStore, dict]:
    """Healthy shadow-active plane written with the production primitives."""
    authority_id = ca._PRODUCTION_AUTHORITY_ID
    store = ca._AuthorityStore._connect_new(authority_dir, authority_id, test_only=False)
    paths = store.test_paths
    descriptor = "sha256:" + "d" * 64
    request_digest = "sha256:" + "7" * 64
    request_id = "3f0a1e64-6f2b-4b0b-9a52-0d1d4f7a1111"
    issued_at = ca._utc_now()
    receipt = {
        "schema": "claims-authority-receipt/v2",
        "authority_id": authority_id,
        "security_level": "R0_COOPERATIVE",
        "publishable": False,
        "sequence": 1,
        "previous_receipt_digest": None,
        "issued_at": issued_at,
        "operation": "activate-shadow",
        "request_id": request_id,
        "request_digest": request_digest,
        "descriptor_digest": descriptor,
    }
    receipt["receipt_id"] = ca.canonical_digest(
        {"authority_id": authority_id, "sequence": 1, "request_id": request_id, "operation": "activate-shadow"}
    )
    receipt["receipt_digest"] = ca.canonical_digest(receipt)
    connection = store._connection
    connection.execute(
        "INSERT INTO receipts(authority_id, sequence, receipt_id, previous_receipt_digest, receipt_json, receipt_digest, recorded_at) VALUES(?,?,?,?,?,?,?)",
        (
            authority_id,
            1,
            receipt["receipt_id"],
            None,
            ca.canonical_json(receipt),
            receipt["receipt_digest"],
            issued_at,
        ),
    )
    connection.execute(
        "INSERT INTO activation(authority_id, operating_mode, activation_state, descriptor_digest, activated_at, activation_receipt_digest) VALUES(?, 'shadow', 'shadow-active', ?, ?, ?)",
        (authority_id, descriptor, issued_at, receipt["receipt_digest"]),
    )
    connection.execute(
        "UPDATE authority_meta SET epoch=1, descriptor_digest=?, last_sequence=1, last_receipt_digest=?, last_broker_time=? WHERE authority_id=?",
        (descriptor, receipt["receipt_digest"], issued_at, authority_id),
    )
    ca._atomic_write_json(
        paths.high_water,
        ca._high_water_payload(
            authority_id, sequence=1, receipt_digest=receipt["receipt_digest"], descriptor_digest=descriptor
        ),
    )
    ca._atomic_write_json(
        paths.activation_witness,
        ca._witness_payload(
            authority_id,
            state="shadow-active",
            sequence=1,
            descriptor_digest=descriptor,
            activation_receipt_digest=receipt["receipt_digest"],
            request_digest=request_digest,
        ),
    )
    return paths, store, receipt


@pytest.fixture()
def env(tmp_path, monkeypatch) -> Env:
    monkeypatch.setattr(ca, "wal_allowed_for_current", lambda: True)
    module = _load_module()
    paths, store, receipt = _build_plane(tmp_path / "authority")
    # Provision a fixture restore base through the official backup path and
    # pin it the same way the deployed sampler is pinned.
    backup = store.backup_now(timestamp="2026-09-27T04:00:00+00:00")
    store._connection.close()
    monkeypatch.setattr(module, "RESTORE_BASE_DATABASE", Path(backup["database"]).name)
    monkeypatch.setattr(module, "RESTORE_BASE_MANIFEST", Path(backup["manifest"]).name)
    monkeypatch.setattr(
        module,
        "RESTORE_BASE_STORE_DIGEST",
        "sha256:" + hashlib.sha256(Path(backup["database"]).read_bytes()).hexdigest(),
    )
    return Env(module=module, paths=paths, obs=tmp_path / "obs", receipt=receipt)


def _alerts(env: Env) -> list[dict]:
    path = env.obs / "alerts.jsonl"
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


# ── detection ───────────────────────────────────────────────────────────


def test_detects_healthy_shadow_active_plane(env: Env) -> None:
    report = env.module.verify_authority_plane(env.paths)
    assert report["ok"] is True, report["error"]
    assert report["checks"]["receipt_chain"] == {"sequence": 1, "tip": env.receipt["receipt_digest"]}
    assert report["checks"]["high_water"]["database_sequence"] == 1
    assert report["checks"]["activation_witness"]["state"] == "shadow-active"


def test_verification_is_strictly_read_only(env: Env) -> None:
    watched = [env.paths.store, env.paths.high_water, env.paths.activation_witness]
    before = {p: (p.stat().st_mtime_ns, p.stat().st_size, p.read_bytes()) for p in watched}
    listing_before = sorted(os.listdir(env.paths.authority_dir))
    assert env.module.verify_authority_plane(env.paths)["ok"] is True
    assert {p: (p.stat().st_mtime_ns, p.stat().st_size, p.read_bytes()) for p in watched} == before
    # sqlite creates its own sidecars for *any* connection on a WAL database
    # (a 0-byte -wal plus the 32 KB -shm index); nothing else may appear, and
    # a 0-byte -wal proves the probe wrote no frames.
    created = set(os.listdir(env.paths.authority_dir)) - set(listing_before)
    assert created <= {"store.sqlite3-wal", "store.sqlite3-shm"}, created
    if "store.sqlite3-wal" in created:
        assert (env.paths.authority_dir / "store.sqlite3-wal").stat().st_size == 0


def test_detects_receipt_byte_flip(env: Env) -> None:
    _byte_flip(env.paths.store, env.receipt["receipt_digest"].encode())
    report = env.module.verify_authority_plane(env.paths)
    assert report["ok"] is False
    assert report["error"]["code"] == "AUTHORITY_STORE_CORRUPT"


def test_detects_in_place_high_water_rewrite(env: Env) -> None:
    """kimi's in-place rewrite shape: required key silently dropped."""
    payload = _read(env.paths.high_water)
    payload.pop("descriptor_digest")
    env.paths.high_water.write_text(json.dumps(payload), encoding="utf-8")
    report = env.module.verify_authority_plane(env.paths)
    assert report["ok"] is False
    assert report["error"]["code"].startswith("AUTHORITY_HIGHWATER")


def test_detects_missing_activation_witness(env: Env) -> None:
    env.paths.activation_witness.unlink()
    report = env.module.verify_authority_plane(env.paths)
    assert report["ok"] is False
    assert report["error"]["code"] == "AUTHORITY_ACTIVATION_WITNESS_INVALID"


# ── snapshot evidence ───────────────────────────────────────────────────


def test_snapshot_copies_store_plane_read_only_with_checksums(env: Env) -> None:
    snapshot = env.module.snapshot_corruption(env.paths, T0)
    directory = Path(snapshot["dir"])
    assert directory.parent == env.paths.backups
    assert directory.name.startswith("incident-20260927T040000Z")
    assert [item["file"] for item in snapshot["files"]] == list(env.module.STORE_PLANE_FILES)
    assert snapshot["missing"] == []
    assert (directory.stat().st_mode & 0o777) == 0o555
    for name in env.module.STORE_PLANE_FILES:
        copied = directory / name
        assert (copied.stat().st_mode & 0o777) == 0o400
        assert copied.read_bytes() == (env.paths.authority_dir / name).read_bytes()
    sums = (directory / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines()
    assert len(sums) == 3
    for line in sums:
        digest, recorded_path = line.split("  ", 1)
        target = Path(recorded_path)
        assert digest == hashlib.sha256(target.read_bytes()).hexdigest()
        assert target.parent == directory


# ── restore source digest ───────────────────────────────────────────────


def test_restore_source_accepts_pinned_backup(env: Env) -> None:
    report = env.module.verify_restore_source(env.paths)
    assert report["ok"] is True, report["error"]
    assert report["checks"]["manifest_digest"] == "ok"
    assert report["checks"]["store_digest"] == "ok"
    assert report["checks"]["rebuilt_plane"]["receipt_chain"]["sequence"] == 1


def test_restore_source_rejects_tampered_manifest(env: Env) -> None:
    manifest_path = env.paths.backups / env.module.RESTORE_BASE_MANIFEST
    manifest = _read(manifest_path)
    manifest["sequence"] = 99
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    report = env.module.verify_restore_source(env.paths)
    assert report["ok"] is False
    assert "manifest_digest_mismatch" in report["error"]["detail"]


def test_restore_source_rejects_tampered_database(env: Env) -> None:
    database = env.paths.backups / env.module.RESTORE_BASE_DATABASE
    _byte_flip(database, b"SQLite format 3")  # file header magic
    report = env.module.verify_restore_source(env.paths)
    assert report["ok"] is False
    assert "store_digest_mismatch_pinned" in report["error"]["detail"]


def test_restore_source_pins_expected_digest(env: Env) -> None:
    digest = env.module.RESTORE_BASE_STORE_DIGEST
    assert digest.startswith("sha256:") and len(digest) == len("sha256:") + 64
    assert env.module.verify_restore_source(env.paths, store_digest="sha256:" + "0" * 64)["ok"] is False


# ── full cycle ──────────────────────────────────────────────────────────


def test_watchdog_detects_snapshots_alerts_and_restores(env: Env) -> None:
    healthy_bytes = env.paths.store.read_bytes()
    _byte_flip(env.paths.store, env.receipt["receipt_digest"].encode())
    corrupted_bytes = env.paths.store.read_bytes()
    assert corrupted_bytes != healthy_bytes
    assert env.module.verify_authority_plane(env.paths)["ok"] is False

    report = env.module.run_watchdog(env.paths, env.obs, moment=T0)

    assert report["detected"] is True
    assert report["action"] == "restore_attempted"
    assert report["restore"]["outcome"] == "success"
    assert report["ok"] is True
    assert env.module.verify_authority_plane(env.paths)["ok"] is True
    # the store is rebuilt byte-for-byte from the pinned backup (sqlite's own
    # header change counter may differ from the pre-corruption live file)
    restored_bytes = env.paths.store.read_bytes()
    assert restored_bytes == (env.paths.backups / env.module.RESTORE_BASE_DATABASE).read_bytes()
    assert restored_bytes != corrupted_bytes

    snapshot = Path(report["snapshot"]["dir"])
    assert snapshot.is_dir()
    assert snapshot.parent == env.paths.backups
    # evidence keeps the corrupt bytes, not the repaired ones
    assert (snapshot / "store.sqlite3").read_bytes() != env.paths.store.read_bytes()

    kinds = [record["kind"] for record in _alerts(env)]
    assert kinds == ["restore_attempt", "restore_outcome", "corruption_detected"]
    outcome = next(record for record in _alerts(env) if record["kind"] == "restore_outcome")
    assert outcome["outcome"] == "success"
    assert outcome["reverify"]["ok"] is True
    detection = next(record for record in _alerts(env) if record["kind"] == "corruption_detected")
    assert detection["auto_restore_base"]["database"] == env.module.RESTORE_BASE_DATABASE

    summary = env.module.watchdog_summary(report)
    assert summary["ok"] is True
    assert summary["restore_outcome"] == "success"
    assert summary["snapshot"] == str(snapshot)


def test_watchdog_healthy_tick_writes_nothing(env: Env) -> None:
    report = env.module.run_watchdog(env.paths, env.obs, moment=T0)
    assert report["ok"] is True
    assert report["detected"] is False
    assert report["action"] == "monitor_healthy"
    assert not (env.obs / "alerts.jsonl").exists()
    assert not list(env.paths.backups.glob("incident-*"))


# ── cooldown rails ──────────────────────────────────────────────────────


def test_second_restore_is_suppressed_by_cooldown(env: Env) -> None:
    _byte_flip(env.paths.store, env.receipt["receipt_digest"].encode())
    first = env.module.run_watchdog(env.paths, env.obs, moment=T0)
    assert first["restore"]["outcome"] == "success"

    # corrupt again inside the 30 minute window: detect, but never fight a writer
    _byte_flip(env.paths.store, env.receipt["receipt_digest"].encode())
    second = env.module.run_watchdog(env.paths, env.obs, moment=T0 + timedelta(seconds=60))
    assert second["detected"] is True
    assert second["action"] == "suppressed_cooldown"
    assert second["restore"] is None
    assert second["ok"] is False
    assert sum(1 for record in _alerts(env) if record["kind"] == "restore_attempt") == 1
    # evidence window still throttled to one detection record
    assert sum(1 for record in _alerts(env) if record["kind"] == "corruption_detected") == 1

    # after the window the auto-restore re-arms and heals
    third = env.module.run_watchdog(env.paths, env.obs, moment=T0 + timedelta(minutes=31))
    assert third["action"] == "restore_attempted"
    assert third["restore"]["outcome"] == "success"
    assert env.module.verify_authority_plane(env.paths)["ok"] is True


def test_failed_restore_blocks_further_attempts_until_forced(env: Env, monkeypatch) -> None:
    monkeypatch.setattr(env.module, "RESTORE_BASE_STORE_DIGEST", "sha256:" + "0" * 64)
    _byte_flip(env.paths.store, env.receipt["receipt_digest"].encode())

    first = env.module.run_watchdog(env.paths, env.obs, moment=T0)
    assert first["restore"]["outcome"] == "refused_source_invalid"
    assert first["ok"] is False

    _byte_flip(env.paths.store, env.receipt["receipt_digest"].encode())
    second = env.module.run_watchdog(env.paths, env.obs, moment=T0 + timedelta(minutes=31))
    assert second["action"] == "suppressed_after_failure"
    assert second["restore"] is None
    assert sum(1 for record in _alerts(env) if record["kind"] == "restore_attempt") == 1

    forced = env.module.run_watchdog(env.paths, env.obs, moment=T0 + timedelta(minutes=62), force_restore=True)
    assert forced["restore"]["outcome"] == "refused_source_invalid"
    assert sum(1 for record in _alerts(env) if record["kind"] == "restore_attempt") == 2


def test_blocked_when_snapshot_fails(env: Env, monkeypatch) -> None:
    """Evidence first: no restore without a snapshot."""
    monkeypatch.setattr(env.module, "snapshot_corruption", lambda *args, **kwargs: {"error": "OSError: disk full"})
    _byte_flip(env.paths.store, env.receipt["receipt_digest"].encode())
    report = env.module.run_watchdog(env.paths, env.obs, moment=T0)
    assert report["action"] == "blocked_snapshot_failed"
    assert report["restore"] is None
    assert report["ok"] is False
    detection = next(record for record in _alerts(env) if record["kind"] == "corruption_detected")
    assert detection["snapshot"]["error"] == "OSError: disk full"


# ── repair tiers ────────────────────────────────────────────────────────


def _advance_plane(env: Env, store) -> dict:
    """Append a legitimate sequence-2 receipt (a writer that got ahead)."""
    authority_id = ca._PRODUCTION_AUTHORITY_ID
    issued_at = ca._utc_now()
    receipt = {
        "schema": "claims-authority-receipt/v2",
        "authority_id": authority_id,
        "security_level": "R0_COOPERATIVE",
        "publishable": False,
        "sequence": 2,
        "previous_receipt_digest": env.receipt["receipt_digest"],
        "issued_at": issued_at,
        "operation": "observe-shadow",
        "request_id": "3f0a1e64-6f2b-4b0b-9a52-0d1d4f7a2222",
        "request_digest": "sha256:" + "8" * 64,
        "descriptor_digest": "sha256:" + "d" * 64,
    }
    receipt["receipt_id"] = ca.canonical_digest(
        {
            "authority_id": authority_id,
            "sequence": 2,
            "request_id": receipt["request_id"],
            "operation": "observe-shadow",
        }
    )
    receipt["receipt_digest"] = ca.canonical_digest(receipt)
    connection = store._connection
    connection.execute(
        "INSERT INTO receipts(authority_id, sequence, receipt_id, previous_receipt_digest, receipt_json, receipt_digest, recorded_at) VALUES(?,?,?,?,?,?,?)",
        (
            authority_id,
            2,
            receipt["receipt_id"],
            env.receipt["receipt_digest"],
            ca.canonical_json(receipt),
            receipt["receipt_digest"],
            issued_at,
        ),
    )
    connection.execute(
        "UPDATE authority_meta SET last_sequence=2, last_receipt_digest=?, last_broker_time=? WHERE authority_id=?",
        (receipt["receipt_digest"], issued_at, authority_id),
    )
    ca._atomic_write_json(
        env.paths.high_water,
        ca._high_water_payload(
            authority_id, sequence=2, receipt_digest=receipt["receipt_digest"], descriptor_digest="sha256:" + "d" * 64
        ),
    )
    return receipt


def test_plane_rebuild_repairs_derived_files_without_touching_store(env: Env) -> None:
    """Tier 1: chain OK, high-water rewritten -> rebuild derived files only."""
    store_bytes = env.paths.store.read_bytes()
    payload = _read(env.paths.high_water)
    payload.pop("descriptor_digest")
    env.paths.high_water.write_text(json.dumps(payload), encoding="utf-8")
    detection = env.module.verify_authority_plane(env.paths)
    assert detection["ok"] is False
    assert env.module.repair_tier(detection) == "plane_rebuild"

    report = env.module.run_watchdog(env.paths, env.obs, moment=T0)

    assert report["action"] == "restore_attempted"
    assert report["restore"]["tier"] == "plane_rebuild"
    assert report["restore"]["outcome"] == "success"
    assert report["restore"]["stage"] == "rebuilt"
    assert report["restore_source"] is None
    assert report["rollback"] is None
    assert report["ok"] is True
    # receipts were never at risk: the store file is byte-identical
    assert env.paths.store.read_bytes() == store_bytes
    assert env.module.verify_authority_plane(env.paths)["ok"] is True
    attempt = next(record for record in _alerts(env) if record["kind"] == "restore_attempt")
    assert attempt["tier"] == "plane_rebuild"
    assert attempt["database"] is None


def test_full_restore_rolls_back_loudly_when_live_chain_is_ahead(env: Env) -> None:
    """Tier 2 with a writer ahead: restore, but never silently drop receipts."""
    store = ca._AuthorityStore._connect_existing(env.paths, ca._PRODUCTION_AUTHORITY_ID)
    advanced = _advance_plane(env, store)
    store._connection.close()
    assert env.module.verify_authority_plane(env.paths)["ok"] is True

    # chain corruption after the writer advanced
    _byte_flip(env.paths.store, env.receipt["receipt_digest"].encode())
    detection = env.module.verify_authority_plane(env.paths)
    assert detection["ok"] is False
    assert env.module.repair_tier(detection) == "full_restore"

    report = env.module.run_watchdog(env.paths, env.obs, moment=T0)

    assert report["sequences"] == {"live": 2, "pinned": 1}
    assert report["restore"]["tier"] == "full_restore"
    assert report["restore"]["outcome"] == "success"
    assert report["rollback"] == {
        "live_sequence": 2,
        "restored_sequence": 1,
        "snapshot": (report["snapshot"] or {}).get("dir"),
    }
    assert report["ok"] is True
    assert env.module.verify_authority_plane(env.paths)["ok"] is True
    # the rolled-back receipts are preserved as evidence
    snapshot_store = Path(report["snapshot"]["dir"]) / "store.sqlite3"
    assert advanced["receipt_digest"].encode() in snapshot_store.read_bytes()
    rollback = next(record for record in _alerts(env) if record["kind"] == "restore_rollback")
    assert rollback["live_sequence"] == 2 and rollback["restored_sequence"] == 1
    assert env.module.watchdog_summary(report)["rollback"] == report["rollback"]
