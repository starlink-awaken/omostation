# ---
# domain: workflows
# layer: tool
# status: active
# ---
"""Reflection Bridge — connects autonomous_planner pipeline results to existing reflection infrastructure."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# Project root: kairon/ (at runtime.executor/workflows/reflection/bridge.py parents[6])
_PROJECT_ROOT = Path(__file__).resolve().parents[6]
REPORT_DIR = _PROJECT_ROOT / "data" / "planning_results"
_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Kairon OrgMemory for pattern detection
# ---------------------------------------------------------------------------
_HAS_ORG_MEMORY = False
try:
    from runtime.executor.engine_memory import OrgMemory
    _HAS_ORG_MEMORY = True
except ImportError:
    pass

__all__ = [
    "record_retrospective",
    "extract_lessons",
    "detect_patterns",
    "run_reflect",
]

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _load_last_result() -> dict[str, Any]:
    """Load the most recent pipeline result from disk."""
    path = REPORT_DIR / "last_result.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def _fact_graph_db_path() -> str:
    return str(_PROJECT_ROOT / "data" / "db" / "organs" / "memory" / "fact_graph.db")


def _sql_pattern_fallback(db_path: str, min_frequency: int = 2) -> list[dict[str, Any]]:
    import sqlite3
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT sub, COUNT(DISTINCT pred) as pred_count
            FROM fact_triples
            GROUP BY sub
            HAVING pred_count >= ?
        """, (min_frequency,))
        patterns = []
        for row in cursor.fetchall():
            patterns.append({
                "pattern_type": "co_occurrence",
                "entities": [row[0]],
                "frequency": row[1],
                "confidence": 0.5,
            })
        conn.close()
        return patterns
    except Exception as exc:
        _log.debug("SQL pattern fallback failed: %s", exc)
        return []


def _kairon_org_memory_patterns(db_path: str, min_frequency: int = 2) -> list[dict[str, Any]]:
    if not _HAS_ORG_MEMORY:
        return []
    try:
        om = OrgMemory(db_path=db_path)
        summary = om.summarize()
        patterns = []
        for category, info in summary.get("categories", {}).items():
            if info["count"] >= min_frequency:
                patterns.append({
                    "pattern_type": "org_category",
                    "entities": [category],
                    "frequency": info["count"],
                    "confidence": info.get("avg_confidence", 0.5),
                })
        om.close()
        return patterns
    except Exception as exc:
        _log.debug("OrgMemory pattern lookup failed: %s", exc)
        return []


def _detect_patterns_impl() -> list[dict[str, Any]]:
    db_path = _fact_graph_db_path()
    patterns = _kairon_org_memory_patterns(db_path)
    if patterns:
        return patterns
    return _sql_pattern_fallback(db_path)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def record_retrospective(pipeline_result: dict[str, Any] | None = None) -> bool:
    if pipeline_result is None:
        pipeline_result = _load_last_result()

    results_data: dict[str, Any] = pipeline_result.get("results", {})
    what_worked = [name for name, ok in results_data.items() if ok]
    what_failed = [name for name, ok in results_data.items() if not ok]

    try:
        retrospective_data = {
            "timestamp": datetime.now(UTC).isoformat(),
            "iteration_id": pipeline_result.get("goal", ""),
            "what_worked": what_worked,
            "what_failed": what_failed,
        }
        fallback_path = REPORT_DIR / "retrospective_fallback.json"
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        fallback_path.write_text(
            json.dumps(retrospective_data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError as exc:
        _log.debug("Failed to write retrospective: %s", exc)

    return True


def extract_lessons(pipeline_result: dict[str, Any]) -> list[dict[str, Any]]:
    now_iso = datetime.now(UTC).isoformat()
    results_data: dict[str, Any] = pipeline_result.get("results", {})
    lessons: list[dict[str, Any]] = []

    for step_name, ok in results_data.items():
        if ok:
            continue
        lesson: dict[str, Any] = {
            "source": step_name,
            "lesson": f"Pipeline step '{step_name}' failed or returned unexpected result",
            "severity": "high",
            "timestamp": now_iso,
        }
        lessons.append(lesson)

    return lessons


def detect_patterns() -> list[dict[str, Any]]:
    return _detect_patterns_impl()


def run_reflect(goal: str = "", auto: bool = True) -> bool:
    print("  ▶ [reflection] Starting reflection cycle...")

    pipeline_result = _load_last_result()

    print("  ▶ [reflection] Step 1/3: Recording retrospective...")
    record_retrospective(pipeline_result)
    print("  ▶ [reflection] Retrospective recorded.")

    print("  ▶ [reflection] Step 2/3: Extracting lessons...")
    lessons = extract_lessons(pipeline_result)
    print(f"  ▶ [reflection] Extracted {len(lessons)} lessons.")

    print("  ▶ [reflection] Step 3/3: Detecting patterns...")
    patterns = detect_patterns()
    print(f"  ▶ [reflection] Found {len(patterns)} patterns.")

    print("  ▶ [reflection] Reflection cycle complete.")
    return True
