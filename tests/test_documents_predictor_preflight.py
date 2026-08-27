from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "lib" / "documents_predictor_preflight.py"


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args, "--json"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_missing_documents_root_fails_closed(tmp_path: Path) -> None:
    result = _run("--documents-root", str(tmp_path / "Documents"), "--workspace-root", str(tmp_path / "Workspace"))

    payload = json.loads(result.stdout)
    assert result.returncode == 2
    assert payload["schema"] == "documents.predictor-preflight.v1"
    assert payload["status"] == "unavailable"


def test_preflight_preserves_forecast_categories_and_writes_workspace_only(tmp_path: Path) -> None:
    documents = tmp_path / "Documents"
    workspace = tmp_path / "Workspace"
    documents.mkdir()
    workspace.mkdir()
    evidence = workspace / "runtime" / "predictor.json"

    result = _run(
        "--documents-root",
        str(documents),
        "--workspace-root",
        str(workspace),
        "--evidence",
        str(evidence),
        "--today",
        "2026-08-28",
    )

    payload = json.loads(result.stdout)
    assert result.returncode == 1
    assert payload["schema"] == "documents.predictor-preflight.v1"
    assert set(payload["forecast"]) == {"sanyi", "assessment", "quality", "contracts"}
    assert len(payload["forecast"]["assessment"]) == 3
    assert payload["forecast"]["assessment"][0]["month"] == 8
    assert evidence.is_file()
    assert not list(documents.rglob("forecast-*.md"))


def test_evidence_inside_documents_is_rejected(tmp_path: Path) -> None:
    documents = tmp_path / "Documents"
    documents.mkdir()
    result = _run(
        "--documents-root",
        str(documents),
        "--workspace-root",
        str(tmp_path / "Workspace"),
        "--evidence",
        str(documents / "forecast.json"),
    )

    payload = json.loads(result.stdout)
    assert result.returncode == 2
    assert payload["status"] == "unavailable"
    assert not (documents / "forecast.json").exists()
