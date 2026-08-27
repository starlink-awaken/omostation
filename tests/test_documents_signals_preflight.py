from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "bin" / "gac" / "documents-domain-owner-job.py"


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "signals-preflight", *args, "--json"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_missing_signals_file_fails_closed(tmp_path: Path) -> None:
    documents = tmp_path / "Documents"
    workspace = tmp_path / "Workspace"
    documents.mkdir()
    workspace.mkdir()

    result = _run(
        "--documents-root",
        str(documents),
        "--workspace-root",
        str(workspace),
    )

    payload = json.loads(result.stdout)
    assert result.returncode == 2
    assert payload["schema"] == "documents.signals-preflight.v1"
    assert payload["status"] == "unavailable"


def test_classifies_signals_without_mutating_documents(tmp_path: Path) -> None:
    documents = tmp_path / "Documents"
    workspace = tmp_path / "Workspace"
    signals = documents / "@驾驶舱" / "_control" / "SIGNALS.md"
    signals.parent.mkdir(parents=True)
    workspace.mkdir()
    signals.write_text(
        """---\nsignals:\n- message: machine event\n  source: aggregated\n  type: warning\n  ts: '2026-08-01T00:00:00Z'\n- message: human event\n  source: human\n  type: info\n  ts: '2026-08-01T00:00:00Z'\n---\n""",
        encoding="utf-8",
    )
    before = signals.read_bytes()
    evidence = workspace / "runtime" / "signals.json"

    result = _run(
        "--documents-root",
        str(documents),
        "--workspace-root",
        str(workspace),
        "--evidence",
        str(evidence),
    )

    payload = json.loads(result.stdout)
    assert result.returncode == 1
    assert payload["status"] == "findings"
    assert payload["summary"] == {"human": 1, "machine": 1, "total": 2}
    assert evidence.is_file()
    assert signals.read_bytes() == before
    assert not (documents / "@驾驶舱" / "_generated").exists()


def test_human_only_signals_are_healthy(tmp_path: Path) -> None:
    documents = tmp_path / "Documents"
    signals = documents / "@驾驶舱" / "_control" / "SIGNALS.md"
    signals.parent.mkdir(parents=True)
    signals.write_text(
        "signals:\n- message: human event\n  source: user\n  type: info\n---\n",
        encoding="utf-8",
    )

    result = _run("--documents-root", str(documents), "--workspace-root", str(tmp_path))

    payload = json.loads(result.stdout)
    assert result.returncode == 0
    assert payload["status"] == "ok"
    assert payload["summary"] == {"human": 1, "machine": 0, "total": 1}


def test_evidence_inside_documents_is_rejected(tmp_path: Path) -> None:
    documents = tmp_path / "Documents"
    signals = documents / "@驾驶舱" / "_control" / "SIGNALS.md"
    signals.parent.mkdir(parents=True)
    signals.write_text("signals:\n---\n", encoding="utf-8")

    result = _run(
        "--documents-root",
        str(documents),
        "--workspace-root",
        str(tmp_path / "Workspace"),
        "--evidence",
        str(documents / "evidence.json"),
    )

    payload = json.loads(result.stdout)
    assert result.returncode == 2
    assert payload["status"] == "unavailable"
    assert not (documents / "evidence.json").exists()
