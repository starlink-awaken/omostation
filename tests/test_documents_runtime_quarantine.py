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


def _exact_runner_plan(module, tmp_path):
    documents = tmp_path / "Documents"
    inbox = documents / "_inbox"
    inbox.mkdir(parents=True)
    (inbox / "hourly_runner.log").write_bytes(b"")
    (inbox / "hourly_runner_err.log").write_bytes(b"")
    (inbox / "note.md").write_text("human content\n", encoding="utf-8")
    target = tmp_path / "Workspace" / "runtime" / "quarantine" / "runner-logs"
    exact = ["hourly_runner.log", "hourly_runner_err.log"]
    inventory = module._load_exact_inventory(documents, inbox, exact)
    plan = module.build_plan(
        documents_root=documents,
        source_root=inbox,
        target_root=target,
        inventory=inventory,
        consumer_receipt=_consumer_receipt(),
        now="2026-08-31T02:30:00Z",
        selected_kinds={"cache"},
        exact_relative_paths=exact,
    )
    return documents, inbox, target, plan


def test_exact_cache_plan_uses_full_documents_context_and_guards_non_targets(tmp_path):
    module = _load_module()

    _documents, _inbox, _target, plan = _exact_runner_plan(module, tmp_path)

    assert [item["relative_path"] for item in plan["files"]] == [
        "hourly_runner.log",
        "hourly_runner_err.log",
    ]
    assert plan["selection_mode"] == "exact"
    assert plan["selected_kinds"] == ["cache"]
    assert plan["expected_relative_paths"] == ["hourly_runner.log", "hourly_runner_err.log"]
    assert plan["summary"] == {"files": 2, "bytes": 0}
    assert plan["non_target_guard"]["files"] == 1
    assert plan["non_target_guard"]["bytes"] == len("human content\n")


def test_exact_inventory_rejects_unsafe_duplicate_missing_and_content_paths(tmp_path):
    module = _load_module()
    documents = tmp_path / "Documents"
    inbox = documents / "_inbox"
    inbox.mkdir(parents=True)
    (inbox / "hourly_runner.log").write_bytes(b"")
    (inbox / "note.md").write_text("human\n", encoding="utf-8")

    for relative_paths in (["../escape.log"], ["/absolute.log"], ["missing.log"], ["hourly_runner.log"] * 2):
        try:
            module._load_exact_inventory(documents, inbox, relative_paths)
        except module.QuarantineError:
            pass
        else:
            raise AssertionError(f"unsafe exact paths must fail: {relative_paths}")

    inventory = module._load_exact_inventory(documents, inbox, ["note.md"])
    try:
        module.build_plan(
            documents_root=documents,
            source_root=inbox,
            target_root=tmp_path / "target",
            inventory=inventory,
            consumer_receipt=_consumer_receipt(),
            now="2026-08-31T02:30:00Z",
            selected_kinds={"cache"},
            exact_relative_paths=["note.md"],
        )
    except module.QuarantineError as exc:
        assert "exact" in str(exc) or "selected" in str(exc)
    else:
        raise AssertionError("content cannot satisfy exact cache selection")


def test_exact_apply_stops_and_preserves_sources_on_non_target_drift(tmp_path):
    module = _load_module()
    _documents, inbox, target, plan = _exact_runner_plan(module, tmp_path)
    (inbox / "note.md").write_text("changed human content\n", encoding="utf-8")

    try:
        module.apply_plan(plan)
    except module.QuarantineError as exc:
        assert "non-target" in str(exc)
    else:
        raise AssertionError("non-target drift must stop exact apply")

    assert (inbox / "hourly_runner.log").exists()
    assert (inbox / "hourly_runner_err.log").exists()
    assert not target.exists()


def test_completed_manifest_verifies_and_rolls_back_without_mutating_manifest(tmp_path):
    module = _load_module()
    _documents, inbox, target, plan = _exact_runner_plan(module, tmp_path)
    module.apply_plan(plan)
    manifest_path = target / "manifest.json"
    manifest_before = manifest_path.read_bytes()

    verification = module.verify_completed_manifest(manifest_path)

    assert verification["status"] == "verified"
    assert verification["summary"] == {"files": 2, "bytes": 0}
    assert verification["rollback_available"] is True
    assert verification["permanent_deletion"] is False

    receipt = module.rollback_completed_manifest(manifest_path, now="2026-08-31T03:00:00Z")

    assert receipt["schema"] == "documents-runtime-quarantine-rollback/v1"
    assert receipt["status"] == "rolled_back"
    assert (inbox / "hourly_runner.log").exists()
    assert (inbox / "hourly_runner_err.log").exists()
    assert manifest_path.read_bytes() == manifest_before
    assert json.loads((target / "rollback.json").read_text(encoding="utf-8"))["status"] == "rolled_back"


def test_completed_manifest_rejects_unexpected_target_and_rollback_source_collision(tmp_path):
    module = _load_module()
    _documents, inbox, target, plan = _exact_runner_plan(module, tmp_path)
    module.apply_plan(plan)
    manifest_path = target / "manifest.json"
    (target / "unexpected.txt").write_text("unexpected\n", encoding="utf-8")

    try:
        module.verify_completed_manifest(manifest_path)
    except module.QuarantineError as exc:
        assert "target" in str(exc)
    else:
        raise AssertionError("unexpected target must fail verification")

    (target / "unexpected.txt").unlink()
    (inbox / "hourly_runner.log").write_text("collision\n", encoding="utf-8")
    try:
        module.rollback_completed_manifest(manifest_path, now="2026-08-31T03:00:00Z")
    except module.QuarantineError as exc:
        assert "collision" in str(exc) or "source" in str(exc)
    else:
        raise AssertionError("rollback source collision must fail before overwrite")
    assert (target / "hourly_runner.log").exists()


def test_completed_manifest_rejects_source_path_outside_documents_boundary(tmp_path):
    module = _load_module()
    _documents, _inbox, target, plan = _exact_runner_plan(module, tmp_path)
    module.apply_plan(plan)
    manifest_path = target / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"][0]["source"] = str(tmp_path / "outside.log")
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    try:
        module.verify_completed_manifest(manifest_path)
    except module.QuarantineError as exc:
        assert "boundary" in str(exc) or "Documents" in str(exc)
    else:
        raise AssertionError("manifest source outside Documents must fail closed")


def test_cli_exact_plan_apply_verify_and_rollback(tmp_path, capsys):
    module = _load_module()
    documents = tmp_path / "Documents"
    inbox = documents / "_inbox"
    inbox.mkdir(parents=True)
    (inbox / "hourly_runner.log").write_bytes(b"")
    (inbox / "hourly_runner_err.log").write_bytes(b"")
    (inbox / "note.md").write_text("human\n", encoding="utf-8")
    target = tmp_path / "Workspace" / "runtime" / "quarantine" / "runner-logs"
    receipt_path = tmp_path / "consumer.json"
    receipt_path.write_text(json.dumps(_consumer_receipt()), encoding="utf-8")
    common = [
        "--documents-root",
        str(documents),
        "--source-relative",
        "_inbox",
        "--target-root",
        str(target),
        "--consumer-receipt",
        str(receipt_path),
        "--include-relative",
        "hourly_runner.log",
        "--include-relative",
        "hourly_runner_err.log",
        "--artifact-kind",
        "cache",
        "--now",
        "2026-08-31T02:30:00Z",
        "--json",
    ]

    assert module.main(common) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "planned"
    assert module.main([*common, "--apply"]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "completed"
    assert module.main(["--verify-manifest", str(target / "manifest.json"), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "verified"
    assert (
        module.main(
            [
                "--rollback-manifest",
                str(target / "manifest.json"),
                "--now",
                "2026-08-31T03:00:00Z",
                "--json",
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["status"] == "rolled_back"
