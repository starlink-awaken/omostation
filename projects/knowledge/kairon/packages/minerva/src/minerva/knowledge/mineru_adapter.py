"""MinerU adapter — high-quality document parsing for knowledge ingestion.

Uses MinerU CLI for PDF/DOCX/PPTX/XLSX parsing with 95+ accuracy.
Pipeline mode runs on pure CPU/MPS — no GPU/VRAM required.

Install: pip install "mineru[all]" (Python 3.10-3.13)
"""

from __future__ import annotations

import contextlib
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

MINERU_VENV = Path(__file__).parent.parent.parent.parent / ".venv-mineru"
MODELSCOPE_CACHE = Path.home() / "Model" / "mineru"


def is_available() -> bool:
    """Check if MinerU is installed in its venv."""
    mineru_bin = MINERU_VENV / "bin" / "mineru"
    return mineru_bin.exists()


def parse_document(
    input_path: str,
    output_dir: str | None = None,
    backend: str = "pipeline",
    method: str = "auto",
) -> dict:
    """Parse a document using MinerU pipeline mode.

    Args:
        input_path: Path to PDF, DOCX, PPTX, XLSX, or image file.
        output_dir: Output directory. Defaults to a temp dir.
        backend: 'pipeline' (CPU, 85+) | 'vlm-auto-engine' (GPU, 95+)
        method: 'auto' | 'txt' | 'ocr'

    Returns:
        {"status": "ok", "output_dir": "...", "files": [...]}
        or {"status": "error", "message": "..."}
    """
    if not is_available():
        return {
            "status": "error",
            "message": 'MinerU not installed in .venv-mineru. Run: pip install "mineru[all]"',
        }

    input_p = Path(input_path).expanduser()
    if not input_p.exists():
        return {"status": "error", "message": f"File not found: {input_path}"}

    output_p = Path(output_dir).expanduser() if output_dir else Path(input_p.stem + "_mineru_output")
    output_p = output_p.absolute()

    mineru_bin = MINERU_VENV / "bin" / "mineru"

    try:
        import os

        env = os.environ.copy()
        env["MODELSCOPE_CACHE"] = str(MODELSCOPE_CACHE)
        result = subprocess.run(
            [str(mineru_bin), "-p", str(input_p), "-o", str(output_p), "-b", backend, "-m", method],
            capture_output=True,
            text=True,
            timeout=600,
            env=env,
        )
        if result.returncode != 0:
            return {"status": "error", "message": result.stderr[:500]}

        # Find generated markdown files
        md_files = list(output_p.rglob("*.md"))
        return {
            "status": "ok",
            "output_dir": str(output_p),
            "files": [str(f) for f in md_files],
            "count": len(md_files),
        }
    except subprocess.TimeoutExpired:
        return {"status": "error", "message": "MinerU parsing timed out (120s)"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def parse_to_text(input_path: str) -> str:
    """Parse a document and return the combined markdown text.

    Convenience wrapper for ingest pipeline integration.
    """
    with tempfile.TemporaryDirectory() as output_dir:
        result = parse_document(input_path, output_dir=output_dir)
        if result["status"] != "ok":
            return ""

        texts = []
        for fpath in result.get("files", []):
            with contextlib.suppress(Exception):
                texts.append(Path(fpath).read_text())
        return "\n\n".join(texts)


def cleanup_stale_mineru_outputs(root: str | Path = ".", older_than_hours: int = 24) -> int:
    """Delete stale `*_mineru_output` directories below a root path."""

    root_path = Path(root).expanduser()
    if not root_path.exists():
        return 0

    cutoff = time.time() - older_than_hours * 3600
    removed = 0

    for candidate in root_path.rglob("*_mineru_output"):
        if not candidate.is_dir():
            continue
        try:
            newest_mtime = max(entry.stat().st_mtime for entry in [candidate, *candidate.rglob("*")])
        except ValueError:
            newest_mtime = candidate.stat().st_mtime
        if newest_mtime >= cutoff:
            continue
        shutil.rmtree(candidate, ignore_errors=True)
        removed += 1

    return removed
