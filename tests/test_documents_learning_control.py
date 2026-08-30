from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

import pytest

from lib import documents_learning_control as control


def _set_mtime(path: Path, value: date) -> None:
    timestamp = datetime(value.year, value.month, value.day, 12, 0, 0).timestamp()
    os.utime(path, (timestamp, timestamp))


def _concept_root(tmp_path: Path) -> tuple[Path, Path]:
    documents = tmp_path / "Documents"
    concepts = documents / "@学习进化" / "_knowledge" / "50-concepts"
    concepts.mkdir(parents=True)
    return documents, concepts


def test_decay_plan_is_deterministic_and_selects_only_draft_orphans(tmp_path: Path) -> None:
    documents, concepts = _concept_root(tmp_path)
    orphan = concepts / "orphan.md"
    orphan.write_text("---\nstatus: draft\n---\n# orphan\n", encoding="utf-8")
    _set_mtime(orphan, date(2026, 8, 1))
    referenced = concepts / "referenced.md"
    referenced.write_text("---\nstatus: draft\n---\n# referenced\n", encoding="utf-8")
    _set_mtime(referenced, date(2026, 8, 1))
    referrer = concepts / "referrer.md"
    referrer.write_text("referenced.md\n", encoding="utf-8")
    _set_mtime(referrer, date(2026, 8, 29))
    stable = concepts / "stable.md"
    stable.write_text("---\nstatus: stable\n---\n# stable\n", encoding="utf-8")
    _set_mtime(stable, date(2026, 7, 1))
    (concepts / "README.md").write_text("excluded\n", encoding="utf-8")

    first = control.plan_decay(documents, today=date(2026, 8, 30), stale_days=14)
    second = control.plan_decay(documents, today=date(2026, 8, 30), stale_days=14)

    assert first == second
    assert first["operation"] == "decay-mark-stale"
    assert first["status"] == "planned"
    assert [item["relative_path"] for item in first["candidates"]] == ["@学习进化/_knowledge/50-concepts/orphan.md"]
    assert first["candidates"][0]["action"] == "insert_stale_since"
    assert first["candidates"][0]["stale_since"] == "2026-08-30"
    assert first["candidate_count"] == 1
    assert first["fingerprint"].startswith("sha256:")
    assert "# orphan" not in json.dumps(first, ensure_ascii=False)


def test_decay_apply_requires_fingerprint_and_writes_atomic_rollback_manifest(tmp_path: Path) -> None:
    documents, concepts = _concept_root(tmp_path)
    target = concepts / "orphan.md"
    original = "---\nstatus: draft\n---\n# orphan\n"
    target.write_text(original, encoding="utf-8")
    _set_mtime(target, date(2026, 8, 1))
    workspace = tmp_path / "Workspace"
    workspace.mkdir()
    plan = control.plan_decay(documents, today=date(2026, 8, 30), stale_days=14)

    with pytest.raises(control.ControlError, match="fingerprint"):
        control.apply_plan(
            plan, documents_root=documents, workspace_root=workspace, expected_fingerprint="sha256:wrong"
        )
    assert target.read_text(encoding="utf-8") == original

    result = control.apply_plan(
        plan,
        documents_root=documents,
        workspace_root=workspace,
        expected_fingerprint=plan["fingerprint"],
    )

    assert result["status"] == "applied"
    assert "stale_since: 2026-08-30" in target.read_text(encoding="utf-8")
    assert result["rollback_manifest"]
    manifest = json.loads(Path(result["rollback_manifest"]).read_text(encoding="utf-8"))
    assert manifest["status"] == "completed"
    assert manifest["entries"][0]["sha256"] == "sha256:" + hashlib.sha256(original.encode()).hexdigest()
    assert manifest["entries"][0]["mode"] == "0o644"
    assert Path(result["rollback_manifest"]).is_relative_to(workspace)


def test_decay_apply_rolls_back_when_a_later_write_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    documents, concepts = _concept_root(tmp_path)
    first = concepts / "first.md"
    second = concepts / "second.md"
    for path in (first, second):
        path.write_text("---\nstatus: draft\n---\n", encoding="utf-8")
        _set_mtime(path, date(2026, 8, 1))
    workspace = tmp_path / "Workspace"
    workspace.mkdir()
    plan = control.plan_decay(documents, today=date(2026, 8, 30), stale_days=14)
    original_atomic = control._atomic_write
    calls = 0

    def fail_second(path: Path, content: str, mode: int) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("injected write failure")
        original_atomic(path, content, mode)

    monkeypatch.setattr(control, "_atomic_write", fail_second)

    with pytest.raises(control.ControlError, match="rolled back"):
        control.apply_plan(
            plan,
            documents_root=documents,
            workspace_root=workspace,
            expected_fingerprint=plan["fingerprint"],
        )
    assert first.read_text(encoding="utf-8") == "---\nstatus: draft\n---\n"
    assert second.read_text(encoding="utf-8") == "---\nstatus: draft\n---\n"


def test_inbox_plan_preserves_internal_rules_and_defers_external_domains(tmp_path: Path) -> None:
    documents = tmp_path / "Documents"
    inbox = documents / "@学习进化" / "_inbox"
    inbox.mkdir(parents=True)
    (inbox / "技术文章.md").write_text("AI 趋势与 MCP\n", encoding="utf-8")
    (inbox / "工作材料.md").write_text("工作项目进展\n", encoding="utf-8")
    (inbox / "未知.md").write_text("没有分类关键词\n", encoding="utf-8")
    (inbox / "CLAUDE.md").write_text("contract\n", encoding="utf-8")
    (inbox / "inbox-router.sh").write_text("legacy\n", encoding="utf-8")

    plan = control.plan_inbox(documents)
    by_name = {Path(item["relative_path"]).name: item for item in plan["candidates"]}

    assert plan["status"] == "planned"
    assert by_name["技术文章.md"]["target_relative"] == "@学习进化/_archive/灵感顿悟/"
    assert by_name["工作材料.md"]["disposition"] == "deferred_external"
    assert by_name["工作材料.md"]["target_relative"] == "@工作文档/"
    assert by_name["未知.md"]["target_relative"] == "@学习进化/_inbox/_stale/"
    assert (inbox / "技术文章.md").exists()


def test_inbox_apply_rejects_collision_before_moving_anything(tmp_path: Path) -> None:
    documents = tmp_path / "Documents"
    inbox = documents / "@学习进化" / "_inbox"
    target = documents / "@学习进化" / "_archive" / "灵感顿悟"
    inbox.mkdir(parents=True)
    target.mkdir(parents=True)
    source = inbox / "技术文章.md"
    source.write_text("MCP\n", encoding="utf-8")
    (target / source.name).write_text("existing\n", encoding="utf-8")
    workspace = tmp_path / "Workspace"
    workspace.mkdir()
    plan = control.plan_inbox(documents)

    with pytest.raises(control.ControlError, match="collision"):
        control.apply_plan(
            plan,
            documents_root=documents,
            workspace_root=workspace,
            expected_fingerprint=plan["fingerprint"],
        )
    assert source.exists()
    assert (target / source.name).read_text(encoding="utf-8") == "existing\n"


def test_owner_rejects_documents_workspace_overlap_and_cli_defaults_to_dry_run(tmp_path: Path) -> None:
    documents = tmp_path / "Documents"
    (documents / "@学习进化" / "_inbox").mkdir(parents=True)
    with pytest.raises(control.ControlError, match="disjoint"):
        control.plan_inbox(documents, workspace_root=documents)

    workspace = tmp_path / "Workspace"
    workspace.mkdir()
    result = subprocess.run(
        [
            sys.executable,
            "bin/gac/documents-domain-owner-job.py",
            "learning-control",
            "inbox",
            "route",
            "--documents-root",
            str(documents),
            "--workspace-root",
            str(workspace),
            "--json",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["mode"] == "dry-run"
    assert payload["status"] == "planned"
