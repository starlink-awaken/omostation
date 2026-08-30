from __future__ import annotations

import json
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest

from lib import documents_learning_control_plane as plane


def _learning_root(tmp_path: Path) -> tuple[Path, Path]:
    documents = tmp_path / "Documents"
    learning = documents / "@学习进化"
    (learning / "_control").mkdir(parents=True)
    (learning / "_knowledge" / "50-concepts").mkdir(parents=True)
    (learning / "_knowledge" / "40-lessons" / "lessons").mkdir(parents=True)
    (learning / "_inbox").mkdir(parents=True)
    return documents, learning


def _seed_learning(documents: Path) -> None:
    learning = documents / "@学习进化"
    control = learning / "_control"
    (control / "STATE.md").write_text(
        "---\ntitle: state\nstatus: active\ntype: state\nowner: runtime\n---\n", encoding="utf-8"
    )
    (control / "TIMELINE.md").write_text(
        "---\ntitle: timeline\nstatus: active\ntype: timeline\nowner: runtime\n---\n", encoding="utf-8"
    )
    (control / "control-rules.md").write_text("CR01\nCR02\nCR03\n", encoding="utf-8")
    (control / "router.md").write_text("router\n", encoding="utf-8")
    (control / "signals.md").write_text("message: one\n  real: true\nmessage: two\n  real: false\n", encoding="utf-8")
    (learning / "_knowledge" / "10-systems" / "KEMS" / "_control").mkdir(parents=True)
    (learning / "_knowledge" / "10-systems" / "KEMS" / "_control" / "control-rules.md").write_text(
        "rules\n", encoding="utf-8"
    )
    (learning / "_knowledge" / "30-execution").mkdir(parents=True)
    (learning / "_knowledge" / "30-execution" / "lesson.md").write_text("lesson\n", encoding="utf-8")
    (learning / "_knowledge" / "40-lessons" / "lessons" / "2026-08-20-one.md").write_text("lesson\n", encoding="utf-8")
    (learning / "_knowledge" / "50-concepts" / "concept.md").write_text(
        "---\nstatus: draft\n---\nconcept\n", encoding="utf-8"
    )
    (learning / "_inbox" / "incoming.md").write_text("unknown\n", encoding="utf-8")
    (learning / "_inbox" / "CLAUDE.md").write_text("contract\n", encoding="utf-8")


@pytest.mark.parametrize(
    "mode", ["check", "health", "control-loop", "signals", "bus", "sync", "lessons", "decay", "all"]
)
def test_all_control_plane_modes_are_aggregate_and_read_only(tmp_path: Path, mode: str) -> None:
    documents, _ = _learning_root(tmp_path)
    _seed_learning(documents)
    workspace = tmp_path / "Workspace"
    workspace.mkdir()
    before = tuple(sorted(str(path.relative_to(documents)) for path in documents.rglob("*")))

    result = plane.inspect_control_plane(documents, workspace_root=workspace, mode=mode, today=date(2026, 8, 30))

    after = tuple(sorted(str(path.relative_to(documents)) for path in documents.rglob("*")))
    assert result["schema"] == "documents.learning-control-plane.v1"
    assert result["mode"] == mode
    assert result["status"] in {"ok", "attention", "unavailable"}
    assert result["writes_documents"] is False
    assert before == after
    assert "concept\n" not in json.dumps(result, ensure_ascii=False)


def test_all_mode_contains_each_child_summary(tmp_path: Path) -> None:
    documents, _ = _learning_root(tmp_path)
    _seed_learning(documents)
    workspace = tmp_path / "Workspace"
    workspace.mkdir()

    result = plane.inspect_control_plane(documents, workspace_root=workspace, mode="all", today=date(2026, 8, 30))

    assert set(result["checks"]) == {"check", "health", "control-loop", "signals", "bus", "sync", "lessons", "decay"}
    assert result["summary"]["attention_modes"]
    assert result["summary"]["mode_count"] == 8


def test_decay_mode_delegates_to_existing_learning_owner(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    documents, _ = _learning_root(tmp_path)
    workspace = tmp_path / "Workspace"
    workspace.mkdir()
    expected = {"schema": "runtime.documents-learning-decay.v1", "status": "attention", "orphan_concept_count": 4}
    monkeypatch.setattr(plane, "plan_decay", lambda *_args, **_kwargs: expected)

    result = plane.inspect_control_plane(documents, workspace_root=workspace, mode="decay", today=date(2026, 8, 30))

    assert result["delegated_owner"] == "documents-learning-decay"
    assert result["owner_status"] == "attention"
    assert result["orphan_concept_count"] == 4


def test_control_plane_rejects_overlapping_roots(tmp_path: Path) -> None:
    documents, _ = _learning_root(tmp_path)

    with pytest.raises(plane.ControlPlaneError, match="disjoint"):
        plane.inspect_control_plane(documents, workspace_root=documents, mode="health")


def test_installed_owner_entry_is_callable_with_system_python(tmp_path: Path) -> None:
    documents, _ = _learning_root(tmp_path)
    _seed_learning(documents)
    workspace = tmp_path / "Workspace"
    workspace.mkdir()
    result = subprocess.run(
        [
            sys.executable,
            "bin/gac/documents-domain-owner-job.py",
            "learning-control-plane",
            "health",
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

    assert result.returncode in {0, 1}
    payload = json.loads(result.stdout)
    assert payload["schema"] == "documents.learning-control-plane.v1"
    assert payload["mode"] == "health"
    assert payload["writes_documents"] is False
