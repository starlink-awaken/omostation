from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "bin" / "gac" / "documents-domain-owner-job.py"


def _fake_tesseract(tmp_path: Path, *, language: str = "chi_sim") -> Path:
    tool_dir = tmp_path / "bin"
    tool_dir.mkdir()
    tool = tool_dir / "tesseract"
    tool.write_text(f"#!/bin/sh\nprintf '%s\\n' {language}\n", encoding="utf-8")
    tool.chmod(tool.stat().st_mode | stat.S_IXUSR)
    return tool_dir


def _run(tmp_path: Path, *args: str, tesseract_dir: Path | None = None) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    if tesseract_dir is not None:
        environment["PATH"] = str(tesseract_dir)
    return subprocess.run(
        [sys.executable, str(SCRIPT), "ocr-preflight", *args, "--json"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        env=environment,
    )


def test_ready_source_returns_zero_without_running_ocr(tmp_path: Path) -> None:
    documents = tmp_path / "Documents"
    source = documents / "@工作文档" / "卫健委" / "_storage" / "ocr"
    source.mkdir(parents=True)
    (source / "scan-01.png").write_bytes(b"not an OCR input in this test")
    tool_dir = _fake_tesseract(tmp_path)
    evidence = tmp_path / "workspace" / "ready.json"

    result = _run(
        tmp_path,
        "--documents-root",
        str(documents),
        "--source-relative",
        "@工作文档/卫健委/_storage/ocr",
        "--workspace-root",
        str(tmp_path / "workspace"),
        "--evidence",
        str(evidence),
        tesseract_dir=tool_dir,
    )

    payload = json.loads(result.stdout)
    assert result.returncode == 0
    assert payload["schema"] == "documents.ocr-preflight.v1"
    assert payload["status"] == "ready"
    assert payload["source"]["files"] == 1
    assert evidence.is_file()


def test_missing_source_is_truthful_finding_and_does_not_execute(tmp_path: Path) -> None:
    documents = tmp_path / "Documents"
    documents.mkdir()

    result = _run(
        tmp_path,
        "--documents-root",
        str(documents),
        "--source-relative",
        "@工作文档/卫健委/_storage/missing-ocr",
    )

    payload = json.loads(result.stdout)
    assert result.returncode == 1
    assert payload["status"] == "findings"
    assert payload["source"]["status"] == "missing"
    assert payload["source"]["files"] == 0


def test_invalid_source_path_fails_closed(tmp_path: Path) -> None:
    documents = tmp_path / "Documents"
    documents.mkdir()

    result = _run(tmp_path, "--documents-root", str(documents), "--source-relative", "../outside")

    payload = json.loads(result.stdout)
    assert result.returncode == 2
    assert payload["status"] == "unavailable"
    assert "source-relative" in payload["errors"][0]


def test_engine_missing_returns_one_and_preserves_documents(tmp_path: Path) -> None:
    documents = tmp_path / "Documents"
    source = documents / "ocr"
    source.mkdir(parents=True)
    sample = source / "scan.pdf"
    sample.write_bytes(b"sample")
    before = sample.read_bytes()
    evidence = tmp_path / "workspace" / "engine.json"

    result = _run(
        tmp_path,
        "--documents-root",
        str(documents),
        "--source-relative",
        "ocr",
        "--workspace-root",
        str(tmp_path / "workspace"),
        "--evidence",
        str(evidence),
        tesseract_dir=tmp_path / "no-tesseract",
    )

    payload = json.loads(result.stdout)
    assert result.returncode == 1
    assert payload["status"] == "findings"
    assert payload["engine"]["status"] == "missing"
    assert sample.read_bytes() == before
    assert evidence.is_file()
