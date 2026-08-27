from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "bin" / "gac" / "documents-domain-owner-job.py"


def _fixture(tmp_path: Path, *, markers: bool = True) -> tuple[Path, Path]:
    documents = tmp_path / "Documents"
    workspace = tmp_path / "Workspace"
    dashboard = documents / "@驾驶舱" / "_control" / "DASHBOARD.md"
    dashboard.parent.mkdir(parents=True)
    (workspace / ".omo" / "state").mkdir(parents=True)
    (workspace / "data" / "cards").mkdir(parents=True)
    (workspace / ".omo" / "state" / "system.yaml").write_text("status: ok\n", encoding="utf-8")
    (workspace / ".omo" / "state" / "health.yaml").write_text("health: ok\n", encoding="utf-8")
    (workspace / "data" / "cards" / "cards.db").write_bytes(b"sqlite-placeholder")
    dashboard.write_text(
        "before\n"
        "<!-- AUTOGEN:WORKSPACE-BRIDGE BEGIN (bridge-refresh.py · 勿手改) -->\n"
        "bridge\n"
        "<!-- AUTOGEN:WORKSPACE-BRIDGE END -->\n"
        "<!-- AUTOGEN:CARDS-VIEW BEGIN (bridge-refresh.py · 勿手改) -->\n"
        "cards\n"
        "<!-- AUTOGEN:CARDS-VIEW END -->\n"
        "after\n",
        encoding="utf-8",
    )
    if not markers:
        dashboard.write_text("ordinary dashboard\n", encoding="utf-8")
    return documents, workspace


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "bridge-preflight", *args, "--json"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_ready_bridge_returns_zero_and_bounded_summary(tmp_path: Path) -> None:
    documents, workspace = _fixture(tmp_path)
    evidence = workspace / "evidence" / "bridge.json"
    dashboard_before = (documents / "@驾驶舱/_control/DASHBOARD.md").read_bytes()

    result = _run(
        "--documents-root",
        str(documents),
        "--workspace-root",
        str(workspace),
        "--evidence",
        str(evidence),
    )

    payload = json.loads(result.stdout)
    assert result.returncode == 0
    assert payload["schema"] == "documents.bridge-preflight.v1"
    assert payload["status"] == "ready"
    assert payload["summary"] == {"sources_ready": 3, "markers_ready": 2}
    assert "bridge\n" not in payload["sources"]
    assert dashboard_before == (documents / "@驾驶舱/_control/DASHBOARD.md").read_bytes()
    assert evidence.is_file()


def test_missing_marker_is_truthful_finding(tmp_path: Path) -> None:
    documents, workspace = _fixture(tmp_path, markers=False)

    result = _run("--documents-root", str(documents), "--workspace-root", str(workspace))

    payload = json.loads(result.stdout)
    assert result.returncode == 1
    assert payload["status"] == "findings"
    assert payload["summary"]["sources_ready"] == 3
    assert payload["summary"]["markers_ready"] == 0


def test_overlapping_roots_fail_closed(tmp_path: Path) -> None:
    documents, _workspace = _fixture(tmp_path)
    result = _run("--documents-root", str(documents), "--workspace-root", str(documents / "@驾驶舱"))

    payload = json.loads(result.stdout)
    assert result.returncode == 2
    assert payload["status"] == "unavailable"
    assert "disjoint" in payload["errors"][0]


def test_evidence_inside_documents_is_rejected(tmp_path: Path) -> None:
    documents, workspace = _fixture(tmp_path)
    result = _run(
        "--documents-root",
        str(documents),
        "--workspace-root",
        str(workspace),
        "--evidence",
        str(documents / "evidence.json"),
    )

    payload = json.loads(result.stdout)
    assert result.returncode == 2
    assert payload["status"] == "unavailable"
    assert not (documents / "evidence.json").exists()
