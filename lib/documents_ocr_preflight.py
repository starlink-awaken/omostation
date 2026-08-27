#!/usr/bin/env python3
"""Workspace-owned OCR readiness check; deliberately never runs OCR."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

SCHEMA = "documents.ocr-preflight.v1"
_INPUT_SUFFIXES = (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".pdf")


def _payload(status: str, *, source: dict[str, Any], engine: dict[str, Any], errors: list[str] | None = None) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "status": status,
        "source": source,
        "engine": engine,
        "errors": sorted(set(errors or [])),
    }


def _resolve_source(documents_root: Path, source_relative: str) -> Path:
    relative = Path(source_relative)
    if relative.is_absolute() or not source_relative or ".." in relative.parts or relative == Path("."):
        raise ValueError("source-relative must be a non-empty relative path without ..")
    root = documents_root.expanduser().resolve()
    source = (root / relative).resolve()
    if not source.is_relative_to(root):
        raise ValueError("source-relative must remain below Documents root")
    if source.is_symlink():
        raise ValueError("OCR source must not be a symlink")
    return source


def _probe_engine() -> dict[str, Any]:
    executable = shutil.which("tesseract")
    if executable is None:
        return {"status": "missing", "language": "chi_sim", "command": "tesseract"}
    try:
        result = subprocess.run(
            [executable, "--list-langs"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"status": "unavailable", "language": "chi_sim", "command": "tesseract", "error": str(exc)}
    languages = {line.strip() for line in result.stdout.splitlines() if line.strip() and not line.startswith("List of")}
    return {
        "status": "ready" if result.returncode == 0 and "chi_sim" in languages else "missing",
        "language": "chi_sim",
        "command": "tesseract",
    }


def inspect(documents_root: Path, source_relative: str) -> dict[str, Any]:
    try:
        source = _resolve_source(documents_root, source_relative)
    except (OSError, ValueError) as exc:
        return _payload(
            "unavailable",
            source={"relative": source_relative, "status": "invalid", "files": 0},
            engine={"status": "not_checked", "language": "chi_sim", "command": "tesseract"},
            errors=[f"source-relative: {exc}"],
        )
    if not source.is_dir():
        source_result = {"relative": source_relative, "status": "missing", "files": 0}
    else:
        try:
            files = sum(1 for path in source.rglob("*") if path.is_file() and path.suffix.lower() in _INPUT_SUFFIXES)
        except OSError as exc:
            return _payload(
                "unavailable",
                source={"relative": source_relative, "status": "unavailable", "files": 0},
                engine={"status": "not_checked", "language": "chi_sim", "command": "tesseract"},
                errors=[f"OCR source unreadable: {exc}"],
            )
        source_result = {"relative": source_relative, "status": "ready", "files": files}
    engine_result = _probe_engine()
    ready = source_result["status"] == "ready" and engine_result["status"] == "ready"
    return _payload("ready" if ready else "findings", source=source_result, engine=engine_result)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--documents-root", type=Path, default=Path.home() / "Documents")
    parser.add_argument("--source-relative", required=True)
    parser.add_argument("--workspace-root", type=Path, default=Path.cwd())
    parser.add_argument("--evidence", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    payload = inspect(args.documents_root, args.source_relative)
    if args.evidence:
        evidence = args.evidence.expanduser().resolve()
        workspace = args.workspace_root.expanduser().resolve()
        documents = args.documents_root.expanduser().resolve()
        if not evidence.is_relative_to(workspace) or evidence.is_relative_to(documents):
            payload = _payload(
                "unavailable",
                source={"relative": args.source_relative, "status": "invalid", "files": 0},
                engine={"status": "not_checked", "language": "chi_sim", "command": "tesseract"},
                errors=["evidence must be under Workspace and outside Documents"],
            )
            print(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) if args.json else "unavailable: invalid evidence path")
            return 2
        evidence.parent.mkdir(parents=True, exist_ok=True)
        evidence.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) if args.json else f"{payload['status']}: {payload['source']['files']} files")
    return 0 if payload["status"] == "ready" else (1 if payload["status"] == "findings" else 2)


if __name__ == "__main__":
    raise SystemExit(main())
