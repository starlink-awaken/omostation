# ruff: noqa: UP006, UP035, UP045 -- fixtures mirror the Python 3.9 production API.

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional, Tuple

import pytest
import yaml

from lib import documents_client_recovery_relocation as relocation

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "bin" / "gac" / "documents-domain-owner-job.py"


@dataclass(frozen=True)
class Layout:
    home: Path
    documents: Path
    source_roots: Tuple[Path, Path]
    target_root: Path
    rollback_receipt: Path


def _sqlite(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    try:
        connection.execute("CREATE TABLE evidence (value TEXT NOT NULL)")
        connection.execute("INSERT INTO evidence VALUES ('preserved')")
        connection.commit()
    finally:
        connection.close()


def _layout(tmp_path: Path) -> Layout:
    home = tmp_path / "home"
    documents = home / "Documents"
    codex = documents / ".codex-optimize-log"
    recovery = documents / ".cc-switch-recovery2"
    codex.mkdir(parents=True)
    recovery.mkdir(parents=True)
    _sqlite(codex / "cc-switch.db.pre-fix")
    (codex / "config.toml.pre-optimize").write_text("model = 'safe'\n", encoding="utf-8")
    (codex / "repair.bin").write_bytes(b"binary-recovery")
    _sqlite(recovery / "current.db")
    (recovery / "full_dump.sql").write_text("BEGIN;\nCOMMIT;\n", encoding="utf-8")
    (recovery / "empty.db").write_bytes(b"")
    (recovery / "settings_row.sql").write_text("INSERT INTO settings VALUES (1);\n", encoding="utf-8")
    target = home / "Library" / "Application Support" / "CC_Switch Recovery" / "2026-08-30"
    return Layout(
        home=home,
        documents=documents,
        source_roots=(codex, recovery),
        target_root=target,
        rollback_receipt=target.parent / "2026-08-30.rollback-receipt.json",
    )


def _paths(layout: Layout) -> relocation.RelocationPaths:
    return relocation.RelocationPaths(
        documents_root=layout.documents,
        source_roots=layout.source_roots,
        target_root=layout.target_root,
        rollback_receipt=layout.rollback_receipt,
    )


def _consumer_receipt(*, forbidden: int = 0, unmatched: int = 0) -> dict:
    return {
        "schema": "documents.consumer-audit.v1",
        "status": "ok",
        "summary": {
            "forbidden_executors": forbidden,
            "unmatched": unmatched,
        },
        "consumers": [],
    }


def _fixture_bytes(layout: Layout) -> int:
    return sum(path.stat().st_size for root in layout.source_roots for path in root.rglob("*") if path.is_file())


def test_plan_inventories_both_exact_roots_and_fingerprints_all_files(tmp_path: Path) -> None:
    layout = _layout(tmp_path)

    plan = relocation.plan_relocation(
        _paths(layout),
        consumer_receipt=_consumer_receipt(),
        source_handles=[],
        available_bytes=10**9,
    )

    assert plan["schema"] == "documents-client-recovery-relocation/v1"
    assert plan["status"] == "planned"
    assert plan["summary"] == {"files": 7, "bytes": _fixture_bytes(layout)}
    assert {item["relative_path"].split("/", 1)[0] for item in plan["files"]} == {
        ".codex-optimize-log",
        ".cc-switch-recovery2",
    }
    assert plan["source_fingerprint"].startswith("sha256:")
    assert plan["sqlite_checks"] == [
        {"relative_path": ".cc-switch-recovery2/current.db", "status": "ok"},
        {"relative_path": ".codex-optimize-log/cc-switch.db.pre-fix", "status": "ok"},
    ]


@pytest.mark.parametrize("bad_node", ("file-symlink", "directory-symlink", "fifo"))
def test_plan_rejects_symlink_and_non_regular_nodes(tmp_path: Path, bad_node: str) -> None:
    layout = _layout(tmp_path)
    root = layout.source_roots[0]
    if bad_node == "file-symlink":
        (root / "link").symlink_to("config.toml.pre-optimize")
    elif bad_node == "directory-symlink":
        (root / "linked-dir").symlink_to(layout.source_roots[1], target_is_directory=True)
    else:
        os.mkfifo(root / "events.pipe")

    with pytest.raises(relocation.RelocationError, match="regular non-symlink"):
        relocation.plan_relocation(
            _paths(layout),
            consumer_receipt=_consumer_receipt(),
            source_handles=[],
            available_bytes=10**9,
        )


def _unsafe_path_variants(layout: Layout) -> Iterable[relocation.RelocationPaths]:
    wrong_source = layout.documents / "wrong-recovery"
    wrong_source.mkdir()
    yield relocation.RelocationPaths(
        documents_root=layout.documents,
        source_roots=(wrong_source, layout.source_roots[1]),
        target_root=layout.target_root,
        rollback_receipt=layout.rollback_receipt,
    )
    active_target = layout.home / "Library" / "Application Support" / "CC_Switch" / "Recovery"
    yield relocation.RelocationPaths(
        documents_root=layout.documents,
        source_roots=layout.source_roots,
        target_root=active_target,
        rollback_receipt=active_target.parent / "rollback.json",
    )
    external_target = layout.home / "tmp" / "recovery"
    yield relocation.RelocationPaths(
        documents_root=layout.documents,
        source_roots=layout.source_roots,
        target_root=external_target,
        rollback_receipt=external_target.parent / "rollback.json",
    )


def test_plan_rejects_wrong_source_names_target_boundary_and_active_data_overlap(tmp_path: Path) -> None:
    layout = _layout(tmp_path)

    for paths in _unsafe_path_variants(layout):
        with pytest.raises(relocation.RelocationError, match="boundary"):
            relocation.plan_relocation(
                paths,
                consumer_receipt=_consumer_receipt(),
                source_handles=[],
                available_bytes=10**9,
            )


def test_plan_rejects_open_handles(tmp_path: Path) -> None:
    layout = _layout(tmp_path)

    with pytest.raises(relocation.RelocationError, match="open handle"):
        relocation.plan_relocation(
            _paths(layout),
            consumer_receipt=_consumer_receipt(),
            source_handles=[str(layout.source_roots[0] / "cc-switch.db.pre-fix")],
            available_bytes=10**9,
        )


def test_plan_rejects_insufficient_disk(tmp_path: Path) -> None:
    layout = _layout(tmp_path)

    with pytest.raises(relocation.RelocationError, match="insufficient disk"):
        relocation.plan_relocation(
            _paths(layout),
            consumer_receipt=_consumer_receipt(),
            source_handles=[],
            available_bytes=1,
        )


@pytest.mark.parametrize(
    "receipt",
    (
        {"schema": "wrong", "status": "ok", "summary": {"forbidden_executors": 0, "unmatched": 0}},
        _consumer_receipt(forbidden=1),
        _consumer_receipt(unmatched=1),
    ),
)
def test_plan_rejects_unhealthy_consumer_receipt(tmp_path: Path, receipt: dict) -> None:
    layout = _layout(tmp_path)

    with pytest.raises(relocation.RelocationError, match="consumer receipt"):
        relocation.plan_relocation(
            _paths(layout),
            consumer_receipt=receipt,
            source_handles=[],
            available_bytes=10**9,
        )


def test_apply_moves_complete_snapshot_through_staging_and_publishes_manifest(tmp_path: Path) -> None:
    layout = _layout(tmp_path)

    result = relocation.apply_relocation(
        _paths(layout),
        consumer_receipt=_consumer_receipt(),
        source_handles=[],
        available_bytes=10**9,
    )

    assert result["status"] == "completed"
    assert not any(root.exists() for root in layout.source_roots)
    assert layout.target_root.is_dir()
    assert not _paths(layout).staging_root.exists()
    manifest = json.loads((layout.target_root / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["target_fingerprint"] == manifest["source_fingerprint"]
    assert manifest["summary"]["files"] == 7
    assert manifest["permanent_deletion"] is False


def _raise_verification_error(*_args: object, **_kwargs: object) -> None:
    raise relocation.RelocationError("target verification failed", code="TARGET_VERIFY_FAILED")


def test_apply_rolls_back_every_move_when_late_verification_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    layout = _layout(tmp_path)
    before = {
        path.relative_to(layout.documents).as_posix(): path.read_bytes()
        for root in layout.source_roots
        for path in root.rglob("*")
        if path.is_file()
    }
    monkeypatch.setattr(relocation, "_verify_staging", _raise_verification_error)

    with pytest.raises(relocation.RelocationError, match="target verification"):
        relocation.apply_relocation(
            _paths(layout),
            consumer_receipt=_consumer_receipt(),
            source_handles=[],
            available_bytes=10**9,
        )

    after = {
        path.relative_to(layout.documents).as_posix(): path.read_bytes()
        for root in layout.source_roots
        for path in root.rglob("*")
        if path.is_file()
    }
    assert after == before
    assert not layout.target_root.exists()
    assert not _paths(layout).staging_root.exists()


def test_apply_rejects_source_drift_without_partial_move(tmp_path: Path) -> None:
    layout = _layout(tmp_path)
    plan = relocation.plan_relocation(
        _paths(layout),
        consumer_receipt=_consumer_receipt(),
        source_handles=[],
        available_bytes=10**9,
    )
    (layout.source_roots[0] / "late.txt").write_text("drift", encoding="utf-8")

    with pytest.raises(relocation.RelocationError, match="source tree changed"):
        relocation.apply_plan(_paths(layout), plan)

    assert all(root.is_dir() for root in layout.source_roots)
    assert not layout.target_root.exists()


def test_sqlite_quick_check_records_preexisting_corruption_for_byte_preservation(tmp_path: Path) -> None:
    layout = _layout(tmp_path)
    corrupt = layout.source_roots[0] / "corrupt.db"
    corrupt.write_bytes(b"SQLite format 3\x00broken")

    plan = relocation.plan_relocation(
        _paths(layout),
        consumer_receipt=_consumer_receipt(),
        source_handles=[],
        available_bytes=10**9,
    )

    record = next(item for item in plan["sqlite_checks"] if item["relative_path"].endswith("corrupt.db"))
    assert record["status"] == "corrupt-preserved"
    assert record["details_sha256"].startswith("sha256:")
    assert sum(item["status"] == "ok" for item in plan["sqlite_checks"]) == 2
    assert corrupt.read_bytes() == b"SQLite format 3\x00broken"
    assert all(root.is_dir() for root in layout.source_roots)
    assert not layout.target_root.exists()


def test_plan_requires_at_least_one_healthy_sqlite_recovery_file(tmp_path: Path) -> None:
    layout = _layout(tmp_path)
    for root in layout.source_roots:
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            with path.open("rb") as stream:
                if stream.read(16) == b"SQLite format 3\x00":
                    path.write_bytes(b"SQLite format 3\x00broken")

    with pytest.raises(relocation.RelocationError, match="at least one healthy SQLite"):
        relocation.plan_relocation(
            _paths(layout),
            consumer_receipt=_consumer_receipt(),
            source_handles=[],
            available_bytes=10**9,
        )


def test_verify_rejects_manifest_target_tamper(tmp_path: Path) -> None:
    layout = _layout(tmp_path)
    relocation.apply_relocation(
        _paths(layout),
        consumer_receipt=_consumer_receipt(),
        source_handles=[],
        available_bytes=10**9,
    )
    target = layout.target_root / ".cc-switch-recovery2" / "full_dump.sql"
    target.write_text("tampered", encoding="utf-8")

    with pytest.raises(relocation.RelocationError, match="target verification"):
        relocation.verify_relocation(_paths(layout), consumer_receipt=_consumer_receipt())


def test_verify_and_rollback_use_manifest_and_never_overwrite_source(tmp_path: Path) -> None:
    layout = _layout(tmp_path)
    relocation.apply_relocation(
        _paths(layout),
        consumer_receipt=_consumer_receipt(),
        source_handles=[],
        available_bytes=10**9,
    )

    verified = relocation.verify_relocation(_paths(layout), consumer_receipt=_consumer_receipt())
    assert verified["status"] == "verified"
    assert verified["source_roots_absent"] is True
    assert verified["rollback_available"] is True

    layout.source_roots[0].mkdir()
    with pytest.raises(relocation.RelocationError, match="source collision"):
        relocation.rollback_relocation(_paths(layout), target_handles=[])
    layout.source_roots[0].rmdir()

    rolled_back = relocation.rollback_relocation(_paths(layout), target_handles=[])
    assert rolled_back["status"] == "rolled_back"
    assert all(root.is_dir() for root in layout.source_roots)
    assert layout.rollback_receipt.is_file()
    assert not layout.target_root.exists()
    assert _fixture_bytes(layout) > 0


def _write_consumer_receipt(tmp_path: Path, receipt: dict) -> Path:
    path = tmp_path / "consumer.json"
    path.write_text(json.dumps(receipt), encoding="utf-8")
    return path


def _run_cli(command: str, layout: Layout, receipt: Optional[Path] = None) -> subprocess.CompletedProcess:
    arguments = [
        sys.executable,
        str(SCRIPT),
        "client-recovery",
        command,
        "--documents-root",
        str(layout.documents),
        "--target-root",
        str(layout.target_root),
        "--rollback-receipt",
        str(layout.rollback_receipt),
        "--json",
    ]
    if receipt is not None:
        arguments.extend(("--consumer-receipt", str(receipt)))
    return subprocess.run(arguments, check=False, capture_output=True, text=True)


def test_cli_plan_emits_structured_json_without_mutation(tmp_path: Path) -> None:
    layout = _layout(tmp_path)
    receipt = _write_consumer_receipt(tmp_path, _consumer_receipt())

    result = _run_cli("plan", layout, receipt)

    payload = json.loads(result.stdout)
    assert result.returncode == 0
    assert payload["schema"] == "documents-client-recovery-relocation/v1"
    assert payload["status"] == "planned"
    assert all(root.is_dir() for root in layout.source_roots)
    assert not layout.target_root.exists()


def test_cli_failure_has_stable_error_code(tmp_path: Path) -> None:
    layout = _layout(tmp_path)
    receipt = _write_consumer_receipt(tmp_path, _consumer_receipt(forbidden=1))

    result = _run_cli("plan", layout, receipt)

    payload = json.loads(result.stdout)
    assert result.returncode == 2
    assert payload == {
        "schema": "documents-client-recovery-relocation-error/v1",
        "status": "error",
        "code": "CONSUMER_RECEIPT_UNHEALTHY",
        "command": "plan",
        "error": "consumer receipt forbidden_executors must equal zero",
    }


def test_cli_apply_verify_and_rollback_dispatch_real_transaction(tmp_path: Path) -> None:
    layout = _layout(tmp_path)
    receipt = _write_consumer_receipt(tmp_path, _consumer_receipt())

    applied = _run_cli("apply", layout, receipt)
    assert applied.returncode == 0
    assert json.loads(applied.stdout)["status"] == "completed"

    verified = _run_cli("verify", layout, receipt)
    assert verified.returncode == 0
    assert json.loads(verified.stdout)["status"] == "verified"

    rolled_back = _run_cli("rollback", layout)
    assert rolled_back.returncode == 0
    assert json.loads(rolled_back.stdout)["status"] == "rolled_back"


def test_required_phase_gate_and_script_registry_cover_recovery_cli() -> None:
    workflow = (ROOT / ".github" / "workflows" / "phase-gate-enforce.yml").read_text(encoding="utf-8")
    registry = ROOT / "bin" / "_registry" / "scripts" / "governance" / "documents-domain-owner-job.yaml"

    for path in (
        "bin/gac/documents-domain-owner-job.py",
        "lib/documents_client_recovery_relocation.py",
        "tests/test_documents_client_recovery_relocation.py",
    ):
        assert path in workflow
    assert registry.is_file()


def test_cc_switch_recovery_roots_have_one_owner_and_valid_lifecycle() -> None:
    registry_path = ROOT / ".omo" / "_truth" / "registry" / "documents-content-plane-migrations.yaml"
    registry = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
    families = {item["id"]: item for item in registry["families"]}
    root = families["root-oneoff-assets"]
    client = families["cc-switch-recovery-state"]

    assert ".codex-optimize-log/**" not in root["source_globs"]
    assert client["source_globs"] == [
        ".codex-optimize-log/**",
        ".cc-switch-recovery2/**",
    ]
    assert client["disposition"] == "relocate"
    assert client["owner"] == "cc-switch"
    assert client["status"] in {"in_progress", "verified"}
    if client["status"] == "verified":
        assert {
            "verified_at",
            "source_fingerprint",
            "target_fingerprint",
            "consumer_scan",
            "rollback_ref",
        } <= set(client["evidence"])
        assert client["transactions"][0]["rollback_available"] is True
        assert client["transactions"][0]["permanent_deletion"] is False
    for source_glob in client["source_globs"]:
        assert sum(source_glob in family.get("source_globs", []) for family in registry["families"]) == 1
