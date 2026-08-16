"""Audit checkers — document extraction and knowledge base helper functions."""

from __future__ import annotations

import re
import subprocess
import zipfile
from pathlib import Path


def _read_wiki(base: Path, rel: str) -> str:
    p = base / rel
    return p.read_text("utf-8", errors="ignore") if p.exists() else ""


def _extract_pdf(fp: Path, n: int = 2000) -> str:
    """Extract text from PDF via pdftotext with magic-pdf fallback."""
    # Method 1: pdftotext (fast, CLI)
    try:
        r = subprocess.run(
            ["pdftotext", "-l", "5", str(fp), "-"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if r.stdout and len(r.stdout.strip()) > 20:
            cn_chars = len(re.findall(r"[一-鿿]", r.stdout))
            if cn_chars > 10:
                return (r.stdout or "")[:n]
    except FileNotFoundError:
        pass
    except Exception:
        pass

    # Method 2: magic-pdf CLI (OCR fallback)
    import glob as _glob
    import tempfile

    try:
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run(
                ["magic-pdf", "-p", str(fp), "-o", tmp],
                capture_output=True,
                text=True,
                timeout=120,
            )
            md_files = _glob.glob(f"{tmp}/**/*.md", recursive=True)
            if md_files:
                t = Path(md_files[0]).read_text("utf-8", errors="ignore")[:n]
                if t.strip():
                    return t
    except Exception:
        pass

    return ""


def _extract_docx(fp: Path, n: int = 2000) -> str:
    try:
        with zipfile.ZipFile(fp) as z:
            xml = z.read("word/document.xml")
            t = re.sub(r"<[^>]+>", "", xml.decode("utf-8", errors="ignore"))
            return re.sub(r"\s+", " ", t).strip()[:n]
    except Exception:
        return ""
