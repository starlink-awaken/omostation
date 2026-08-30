# ruff: noqa: UP006, UP035 -- fixtures mirror the Python 3.9 production API.

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Tuple

import pytest

from lib import documents_client_recovery_relocation as relocation

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "bin" / "gac" / "documents-client-recovery.py"


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
