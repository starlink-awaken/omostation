from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "bin" / "gac" / "documents-domain-owner-job.py"


def _run(tmp_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "convergence-preflight", *args, "--json"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_missing_documents_root_is_fail_closed(tmp_path: Path) -> None:
    result = _run(tmp_path, "--documents-root", str(tmp_path / "missing"))

    payload = json.loads(result.stdout)
    assert result.returncode == 2
    assert payload["schema"] == "documents.convergence-preflight.v1"
    assert payload["status"] == "unavailable"


def test_preflight_writes_only_workspace_evidence(tmp_path: Path) -> None:
    documents = tmp_path / "Documents"
    workspace = tmp_path / "Workspace"
    workspace.mkdir()
    (documents / "@公共" / "_control").mkdir(parents=True)
    (documents / "@工作文档" / "卫健委" / "_control").mkdir(parents=True)
    (documents / "@工作文档" / "卫健委" / "DOMAIN.yaml").write_text(
        "id: health\n", encoding="utf-8"
    )
    for path in (
        documents / "CLAUDE_GLOBAL.md",
        documents / "CLAUDE.md",
        documents / "@公共" / "_control" / "CLAUDE-公约.md",
        documents / "@公共" / "_control" / "DOMAIN-META-MODEL.md",
        documents / "@公共" / "_control" / "REGISTRY.md",
        documents / "@工作文档" / "卫健委" / "CLAUDE.md",
        documents / "@工作文档" / "卫健委" / "_control" / "STATE.md",
    ):
        path.write_text("Workspace registry gateway L4 M1\n", encoding="utf-8")
    registry = documents / "@公共" / "_control" / "L4-DOMAIN-REGISTRY.yaml"
    registry.write_text(
        "manifests:\n  - id: health\n    path: ../../@工作文档/卫健委/DOMAIN.yaml\n",
        encoding="utf-8",
    )
    evidence = workspace / "runtime" / "convergence.json"

    result = _run(
        tmp_path,
        "--documents-root",
        str(documents),
        "--workspace-root",
        str(workspace),
        "--evidence",
        str(evidence),
    )

    payload = json.loads(result.stdout)
    assert result.returncode in (0, 1)
    assert payload["schema"] == "documents.convergence-preflight.v1"
    assert evidence.is_file()
    assert not (documents / "@驾驶舱").exists()
    assert not list(documents.rglob("*history*"))


def test_evidence_inside_documents_is_rejected(tmp_path: Path) -> None:
    documents = tmp_path / "Documents"
    documents.mkdir()
    result = _run(
        tmp_path,
        "--documents-root",
        str(documents),
        "--workspace-root",
        str(tmp_path / "Workspace"),
        "--evidence",
        str(documents / "report.json"),
    )

    payload = json.loads(result.stdout)
    assert result.returncode == 2
    assert payload["status"] == "unavailable"
    assert not (documents / "report.json").exists()
