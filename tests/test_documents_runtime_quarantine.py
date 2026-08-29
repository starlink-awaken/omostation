"""Tests for the reversible Documents public-runtime quarantine transaction."""

from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "lib" / "documents_runtime_quarantine.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("documents_runtime_quarantine", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _consumer_receipt(*, forbidden: int = 0, unmatched: int = 0) -> dict:
    return {
        "schema": "documents.consumer-audit.v1",
        "status": "ok",
        "summary": {
            "forbidden_executors": forbidden,
            "unmatched": unmatched,
        },
        "consumers": [
            {
                "family": "public-runtime",
                "execution_mode": "content-reference",
                "writes_documents": False,
            }
        ],
    }


def _inventory(source: Path) -> list[dict[str, object]]:
    return [
        {
            "path": str(source / "_runtime" / "job.py"),
            "relative_path": "_runtime/job.py",
            "kind": "runtime",
        },
        {
            "path": str(source / "note.md"),
            "relative_path": "note.md",
            "kind": "content",
        },
    ]


def test_preflight_rejects_forbidden_consumer(tmp_path):
    module = _load_module()
    source = tmp_path / "Documents" / "@公共"
    source.mkdir(parents=True)
    receipt = _consumer_receipt(forbidden=1)

    try:
        module.build_plan(
            documents_root=tmp_path / "Documents",
            source_root=source,
            target_root=tmp_path / "Workspace" / "runtime" / "quarantine",
            inventory=_inventory(source),
            consumer_receipt=receipt,
            now="2026-08-29T13:00:00Z",
        )
    except module.QuarantineError as exc:
        assert "forbidden" in str(exc)
    else:
        raise AssertionError("forbidden consumer must stop the transaction")


def test_owner_module_anchors_to_repository_root_from_lib():
    module = _load_module()

    assert module.ROOT == ROOT


def test_preflight_accepts_single_regular_runtime_file_source(tmp_path):
    module = _load_module()
    documents = tmp_path / "Documents"
    source = documents / "@工作文档" / "卫健委" / "cleanup-commit.sh"
    source.parent.mkdir(parents=True)
    source.write_text("#!/bin/sh\necho cleanup\n", encoding="utf-8")

    plan = module.build_plan(
        documents_root=documents,
        source_root=source,
        target_root=tmp_path / "Workspace" / "runtime" / "quarantine",
        inventory=[
            {"path": str(source), "relative_path": source.name, "kind": "runtime"}
        ],
        consumer_receipt=_consumer_receipt(),
        now="2026-08-29T13:00:00Z",
    )

    assert plan["summary"] == {"files": 1, "bytes": source.stat().st_size}
    assert plan["files"][0]["relative_path"] == source.name
    assert plan["files"][0]["node_type"] == "regular"


def test_apply_moves_single_regular_runtime_file_source(tmp_path):
    module = _load_module()
    documents = tmp_path / "Documents"
    source = documents / "@工作文档" / "卫健委" / "cleanup-commit.sh"
    source.parent.mkdir(parents=True)
    source.write_text("#!/bin/sh\necho cleanup\n", encoding="utf-8")
    target = tmp_path / "Workspace" / "runtime" / "quarantine"

    plan = module.build_plan(
        documents_root=documents,
        source_root=source,
        target_root=target,
        inventory=[
            {"path": str(source), "relative_path": source.name, "kind": "runtime"}
        ],
        consumer_receipt=_consumer_receipt(),
        now="2026-08-29T13:00:00Z",
    )
    manifest = module.apply_plan(plan)

    assert not os.path.lexists(source)
    assert (target / source.name).read_text(encoding="utf-8") == "#!/bin/sh\necho cleanup\n"
    assert manifest["summary"]["files"] == 1


def test_preflight_rejects_symlink_as_single_file_source(tmp_path):
    module = _load_module()
    documents = tmp_path / "Documents"
    real_source = documents / "@工作文档" / "卫健委" / "cleanup-commit.sh"
    real_source.parent.mkdir(parents=True)
    real_source.write_text("#!/bin/sh\necho cleanup\n", encoding="utf-8")
    source = real_source.parent / "cleanup-link.sh"
    os.symlink(real_source.name, source)

    try:
        module.build_plan(
            documents_root=documents,
            source_root=source,
            target_root=tmp_path / "Workspace" / "runtime" / "quarantine",
            inventory=[
                {"path": str(source), "relative_path": source.name, "kind": "runtime"}
            ],
            consumer_receipt=_consumer_receipt(),
            now="2026-08-29T13:00:00Z",
        )
    except module.QuarantineError as exc:
        assert "regular file or directory" in str(exc)
    else:
        raise AssertionError("single-file source symlink must be rejected")


def test_preflight_accepts_dangling_symlink_without_following(tmp_path):
    module = _load_module()
    documents = tmp_path / "Documents"
    source = documents / "@工作文档" / "卫健委" / "_runtime"
    source.mkdir(parents=True)
    link = source / "check.py"
    os.symlink("../../../../@公共/_runtime/missing.py", link)

    plan = module.build_plan(
        documents_root=documents,
        source_root=source,
        target_root=tmp_path / "Workspace" / "runtime" / "quarantine",
        inventory=[
            {"path": str(link), "relative_path": "check.py", "kind": "runtime"}
        ],
        consumer_receipt=_consumer_receipt(),
        now="2026-08-29T13:00:00Z",
    )

    assert plan["files"][0]["node_type"] == "symlink"
    assert plan["files"][0]["link_target"] == "../../../../@公共/_runtime/missing.py"


def test_apply_moves_dangling_symlink_and_records_link_target(tmp_path):
    module = _load_module()
    documents = tmp_path / "Documents"
    source = documents / "@工作文档" / "卫健委" / "_runtime"
    source.mkdir(parents=True)
    link = source / "check.py"
    os.symlink("missing.py", link)
    target = tmp_path / "Workspace" / "runtime" / "quarantine"
    plan = module.build_plan(
        documents_root=documents,
        source_root=source,
        target_root=target,
        inventory=[
            {"path": str(link), "relative_path": "check.py", "kind": "runtime"}
        ],
        consumer_receipt=_consumer_receipt(),
        now="2026-08-29T13:00:00Z",
    )

    manifest = module.apply_plan(plan)

    assert not os.path.lexists(link)
    moved = target / "check.py"
    assert moved.is_symlink()
    assert os.readlink(moved) == "missing.py"
    assert manifest["files"][0]["node_type"] == "symlink"
    assert manifest["files"][0]["link_target"] == "missing.py"


def test_apply_moves_only_runtime_and_writes_hash_manifest(tmp_path):
    module = _load_module()
    documents = tmp_path / "Documents"
    source = documents / "@公共"
    runtime = source / "_runtime" / "job.py"
    content = source / "note.md"
    runtime.parent.mkdir(parents=True)
    runtime.write_bytes(b"runtime\n")
    content.write_bytes(b"content\n")
    target = tmp_path / "Workspace" / "runtime" / "quarantine"
    plan = module.build_plan(
        documents_root=documents,
        source_root=source,
        target_root=target,
        inventory=_inventory(source),
        consumer_receipt=_consumer_receipt(),
        now="2026-08-29T13:00:00Z",
    )

    manifest = module.apply_plan(plan)

    assert not runtime.exists()
    assert content.exists()
    assert (target / "_runtime/job.py").read_bytes() == b"runtime\n"
    assert manifest["status"] == "completed"
    assert manifest["summary"] == {"files": 1, "bytes": 8}
    assert json.loads((target / "manifest.json").read_text(encoding="utf-8"))["files"][0]["sha256"]


def test_apply_rejects_target_collision_without_moving_source(tmp_path):
    module = _load_module()
    documents = tmp_path / "Documents"
    source = documents / "@公共"
    runtime = source / "_runtime" / "job.py"
    runtime.parent.mkdir(parents=True)
    runtime.write_bytes(b"runtime\n")
    target = tmp_path / "Workspace" / "runtime" / "quarantine"
    (target / "_runtime").mkdir(parents=True)
    (target / "_runtime/job.py").write_bytes(b"other\n")
    plan = module.build_plan(
        documents_root=documents,
        source_root=source,
        target_root=target,
        inventory=[_inventory(source)[0]],
        consumer_receipt=_consumer_receipt(),
        now="2026-08-29T13:00:00Z",
    )

    try:
        module.apply_plan(plan)
    except module.QuarantineError as exc:
        assert "collision" in str(exc)
    else:
        raise AssertionError("target collision must stop the transaction")
    assert runtime.read_bytes() == b"runtime\n"


def test_preflight_rejects_source_outside_documents_root(tmp_path):
    module = _load_module()
    documents = tmp_path / "Documents"
    documents.mkdir()
    source = tmp_path / "outside"
    source.mkdir()
    (source / "job.py").write_bytes(b"runtime\n")

    try:
        module.build_plan(
            documents_root=documents,
            source_root=source,
            target_root=tmp_path / "Workspace" / "runtime" / "quarantine",
            inventory=[
                {
                    "path": str(source / "job.py"),
                    "relative_path": "job.py",
                    "kind": "runtime",
                }
            ],
            consumer_receipt=_consumer_receipt(),
            now="2026-08-29T13:00:00Z",
        )
    except module.QuarantineError as exc:
        assert "Documents root" in str(exc)
    else:
        raise AssertionError("source outside Documents must stop the transaction")


def test_apply_rejects_nonempty_quarantine_target_before_moving(tmp_path):
    module = _load_module()
    documents = tmp_path / "Documents"
    source = documents / "@公共"
    runtime = source / "_runtime" / "job.py"
    runtime.parent.mkdir(parents=True)
    runtime.write_bytes(b"runtime\n")
    target = tmp_path / "Workspace" / "runtime" / "quarantine"
    target.mkdir(parents=True)
    (target / "unrelated.txt").write_bytes(b"keep\n")
    plan = module.build_plan(
        documents_root=documents,
        source_root=source,
        target_root=target,
        inventory=[_inventory(source)[0]],
        consumer_receipt=_consumer_receipt(),
        now="2026-08-29T13:00:00Z",
    )

    try:
        module.apply_plan(plan)
    except module.QuarantineError as exc:
        assert "target collision" in str(exc)
    else:
        raise AssertionError("non-empty quarantine target must stop the transaction")
    assert runtime.exists()


def test_apply_restores_moved_sources_when_manifest_write_fails(tmp_path, monkeypatch):
    module = _load_module()
    documents = tmp_path / "Documents"
    source = documents / "@公共"
    runtime = source / "_runtime" / "job.py"
    runtime.parent.mkdir(parents=True)
    runtime.write_bytes(b"runtime\n")
    target = tmp_path / "Workspace" / "runtime" / "quarantine"
    plan = module.build_plan(
        documents_root=documents,
        source_root=source,
        target_root=target,
        inventory=[_inventory(source)[0]],
        consumer_receipt=_consumer_receipt(),
        now="2026-08-29T13:00:00Z",
    )

    def fail_manifest(*_args, **_kwargs):
        raise OSError("manifest unavailable")

    monkeypatch.setattr(module, "_write_json", fail_manifest)
    try:
        module.apply_plan(plan)
    except module.QuarantineError as exc:
        assert "manifest unavailable" in str(exc)
    else:
        raise AssertionError("manifest failure must stop and roll back")
    assert runtime.read_bytes() == b"runtime\n"
    assert not (target / "_runtime/job.py").exists()
