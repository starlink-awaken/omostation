"""Research Result Persistence — automatic save and retrieval.

Saves every research result to ~/.minerva/research/{id}/ for permanent storage.
Supports list, show, and delete operations.
"""

from __future__ import annotations

import contextlib
import json
import re
import shutil
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

_RESULTS_DIR = Path.home() / ".minerva" / "research"


def _ensure_dir() -> None:
    _RESULTS_DIR.mkdir(parents=True, exist_ok=True)


def _slugify(query: str, max_len: int = 40) -> str:
    """Create a filesystem-safe slug from a query string."""
    slug = re.sub(r"[^a-zA-Z0-9一-鿿_-]", "_", query.lower())
    slug = re.sub(r"_+", "_", slug).strip("_")
    return slug[:max_len]


def save_research(
    query: str,
    level: str,
    quality_score: int | str,
    source_count: int,
    entity_count: int,
    cost_usd: float,
    elapsed_s: float,
    paradigm_name: str,
    stage_timings: dict[str, float],
    report: str,
    report_path: str | Path | None,
    search_results: list[Any] | None = None,
) -> str:
    """Save a research result to persistent storage.

    Returns the result ID.
    """
    _ensure_dir()
    ts = int(time.time())
    slug = _slugify(query)
    result_id = f"{ts}_{slug}"
    result_dir = _RESULTS_DIR / result_id
    result_dir.mkdir(parents=True, exist_ok=True)

    # Metadata
    meta = {
        "id": result_id,
        "query": query,
        "level": level,
        "timestamp": datetime.now(UTC).isoformat(),
        "quality_score": quality_score,
        "source_count": source_count,
        "entity_count": entity_count,
        "cost_usd": round(cost_usd, 4),
        "elapsed_s": round(elapsed_s, 2),
        "paradigm": paradigm_name,
        "pipeline_stages": {k: round(v, 2) for k, v in stage_timings.items()},
    }
    (result_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    # Report
    if report:
        (result_dir / "report.md").write_text(report, encoding="utf-8")

    # Search results
    if search_results:
        try:
            serializable = []
            for r in search_results[:50]:
                if hasattr(r, "to_dict"):
                    serializable.append(r.to_dict())
                elif hasattr(r, "__dict__"):
                    serializable.append(r.__dict__)
                elif isinstance(r, dict):
                    serializable.append(r)
            if serializable:
                (result_dir / "search_results.json").write_text(
                    json.dumps(serializable, ensure_ascii=False, indent=2, default=str),
                )
        except Exception:
            pass

    # Copy original report if it exists and is different file
    if report_path and str(report_path) != str(result_dir / "report.md"):
        src = Path(report_path)
        if src.exists() and src.is_file():
            shutil.copy2(src, result_dir / "report_original.md")

    return result_id


def list_results(limit: int = 20) -> list[dict[str, Any]]:
    """List all saved research results, newest first."""
    _ensure_dir()
    entries = []
    for d in sorted(_RESULTS_DIR.iterdir(), key=lambda p: p.name, reverse=True):
        if not d.is_dir():
            continue
        meta_file = d / "meta.json"
        if not meta_file.exists():
            continue
        try:
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
            report_file = d / "report.md"
            meta["has_report"] = report_file.exists()
            entries.append(meta)
        except Exception:  # noqa: S112  # defensive fallback
            continue
        if len(entries) >= limit:
            break
    return entries


def get_result(result_id: str) -> dict[str, Any] | None:
    """Get a single research result by ID."""
    result_dir = _RESULTS_DIR / result_id
    if not result_dir.exists() or not result_dir.is_dir():
        return None

    meta_file = result_dir / "meta.json"
    if not meta_file.exists():
        return None

    try:
        meta = json.loads(meta_file.read_text(encoding="utf-8"))
    except Exception:
        return None

    # Load report
    report_file = result_dir / "report.md"
    if report_file.exists():
        meta["report"] = report_file.read_text(encoding="utf-8")

    # Load search results
    results_file = result_dir / "search_results.json"
    if results_file.exists():
        with contextlib.suppress(Exception):
            meta["search_results"] = json.loads(results_file.read_text(encoding="utf-8"))

    return cast("dict[str, Any] | None", meta)


def delete_result(result_id: str) -> bool:
    """Delete a research result. Returns True if deleted."""
    result_dir = _RESULTS_DIR / result_id
    if not result_dir.exists() or not result_dir.is_dir():
        return False
    shutil.rmtree(result_dir)
    return True


def get_storage_stats() -> dict[str, Any]:
    """Get storage statistics."""
    _ensure_dir()
    total = 0
    total_size = 0
    for d in _RESULTS_DIR.iterdir():
        if not d.is_dir():
            continue
        total += 1
        for f in d.rglob("*"):
            if f.is_file():
                total_size += f.stat().st_size
    return {
        "total_results": total,
        "total_size_bytes": total_size,
        "total_size_mb": round(total_size / (1024 * 1024), 2),
        "storage_dir": str(_RESULTS_DIR),
    }
