from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "bin" / "gac" / "documents-domain-owner-job.py"
RULE_IDS = {"CR01", "CR02", "CR03", "CR05", "CR08", "CR23", "CR24", "CR25", "CR26", "CR29", "CR30"}


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "controller-preflight", *args, "--json"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_missing_domain_fails_closed(tmp_path: Path) -> None:
    documents = tmp_path / "Documents"
    workspace = tmp_path / "Workspace"
    documents.mkdir()
    workspace.mkdir()

    result = _run("--documents-root", str(documents), "--workspace-root", str(workspace))

    payload = json.loads(result.stdout)
    assert result.returncode == 2
    assert payload["schema"] == "documents.controller-preflight.v1"
    assert payload["status"] == "unavailable"


def test_controller_preflight_covers_all_rules_without_documents_writes(tmp_path: Path) -> None:
    documents = tmp_path / "Documents"
    workspace = tmp_path / "Workspace"
    domain = documents / "@工作文档" / "卫健委"
    (domain / "_control").mkdir(parents=True)
    (domain / "_entities" / "models").mkdir(parents=True)
    (domain / "_entities" / "ontology").mkdir(parents=True)
    (domain / "_meta").mkdir()
    (domain / "_storage" / "06-工具" / "批量提取" / "ocr_20260731" / "lists").mkdir(parents=True)
    workspace.mkdir()
    (domain / "_control" / "signals.md").write_text(
        "- type: 🔴\n- type: ⚠️\n- type: ⚠️\n- type: ⚠️\n", encoding="utf-8"
    )
    (domain / "_entities" / "facts.md").write_text("last-reviewed: 2026-08-01\n", encoding="utf-8")
    (domain / "_entities" / "models" / "model.md").write_text("last-reviewed: 2026-07-01\n", encoding="utf-8")
    (domain / "_storage" / "06-工具" / "批量提取" / "ocr_20260731" / "lists" / "ocr_01.json").write_text("{}", encoding="utf-8")
    before = sorted(path.relative_to(documents).as_posix() for path in documents.rglob("*"))
    evidence = workspace / "runtime" / "controller.json"

    result = _run(
        "--documents-root",
        str(documents),
        "--workspace-root",
        str(workspace),
        "--domain-relative",
        "@工作文档/卫健委",
        "--evidence",
        str(evidence),
        "--today",
        "2026-08-28",
    )

    payload = json.loads(result.stdout)
    assert result.returncode == 1
    assert payload["schema"] == "documents.controller-preflight.v1"
    assert set(payload["rules"]) == RULE_IDS
    assert payload["rules"]["CR01"]["status"] == "findings"
    assert payload["rules"]["CR02"]["status"] == "findings"
    assert payload["rules"]["CR23"]["status"] == "findings"
    assert payload["rules"]["CR24"]["status"] == "findings"
    assert evidence.is_file()
    after = sorted(path.relative_to(documents).as_posix() for path in documents.rglob("*"))
    assert after == before
    assert not (domain / "_runtime" / "巡检报告").exists()


def test_evidence_inside_documents_is_rejected(tmp_path: Path) -> None:
    documents = tmp_path / "Documents"
    domain = documents / "@工作文档" / "卫健委" / "_control"
    domain.mkdir(parents=True)
    (domain / "signals.md").write_text("signals:\n---\n", encoding="utf-8")
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
