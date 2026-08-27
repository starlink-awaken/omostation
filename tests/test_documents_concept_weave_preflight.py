from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "lib" / "documents_concept_weave_preflight.py"


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args, "--json"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_missing_concept_root_fails_closed(tmp_path: Path) -> None:
    result = _run("--documents-root", str(tmp_path / "Documents"), "--workspace-root", str(tmp_path / "Workspace"))

    payload = json.loads(result.stdout)
    assert result.returncode == 2
    assert payload["schema"] == "documents.concept-weave-preflight.v1"
    assert payload["status"] == "unavailable"


def test_preflight_reports_orphans_and_decay_without_documents_writes(tmp_path: Path) -> None:
    documents = tmp_path / "Documents"
    workspace = tmp_path / "Workspace"
    concepts = documents / "@学习进化" / "_knowledge" / "50-concepts"
    concepts.mkdir(parents=True)
    workspace.mkdir()
    (concepts / "linked.md").write_text("# Linked\n", encoding="utf-8")
    (concepts / "orphan.md").write_text("---\nlast-reviewed: 2026-01-01\n---\n# Orphan\n\n[linked](linked.md)\n", encoding="utf-8")
    bridge_map = documents / "@学习进化" / "_control" / "scripts" / "bridge-map.json"
    bridge_map.parent.mkdir(parents=True)
    bridge_map.write_text("[]", encoding="utf-8")
    before = sorted(path.relative_to(documents).as_posix() for path in documents.rglob("*"))
    evidence = workspace / "runtime" / "concept-weave.json"

    result = _run(
        "--documents-root",
        str(documents),
        "--workspace-root",
        str(workspace),
        "--concept-root-relative",
        "@学习进化/_knowledge/50-concepts",
        "--evidence",
        str(evidence),
        "--today",
        "2026-08-28",
    )

    payload = json.loads(result.stdout)
    assert result.returncode == 1
    assert payload["schema"] == "documents.concept-weave-preflight.v1"
    assert payload["summary"]["concept_files"] == 2
    assert payload["summary"]["orphan_files"] == 1
    assert payload["summary"]["decay_candidates"] == 1
    assert payload["write_capable_operations"] == ["mesh", "bridge", "exec-bridge", "inbox-todo"]
    assert payload["write_capable_status"] == "deferred"
    assert evidence.is_file()
    assert sorted(path.relative_to(documents).as_posix() for path in documents.rglob("*")) == before


def test_evidence_inside_documents_is_rejected(tmp_path: Path) -> None:
    documents = tmp_path / "Documents"
    concepts = documents / "@学习进化" / "_knowledge" / "50-concepts"
    concepts.mkdir(parents=True)
    (concepts / "one.md").write_text("# One\n", encoding="utf-8")
    result = _run(
        "--documents-root",
        str(documents),
        "--workspace-root",
        str(tmp_path / "Workspace"),
        "--evidence",
        str(documents / "bad.json"),
    )

    payload = json.loads(result.stdout)
    assert result.returncode == 2
    assert payload["status"] == "unavailable"
    assert not (documents / "bad.json").exists()
