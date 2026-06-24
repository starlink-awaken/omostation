from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .omo_io import write_text_atomic


def _history_path(workspace_root: Path) -> Path:
    return workspace_root / ".omo" / "_control" / "evolution" / "radar-history.json"


def _day_bucket() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d")


def classify_candidate(candidate: dict[str, Any]) -> bool:
    source = str(candidate.get("source", ""))
    return "(DB unavailable)" not in source and candidate.get("evidence_id") is not None


def load_radar_history(workspace_root: Path) -> dict[str, Any]:
    path = _history_path(workspace_root)
    if not path.exists():
        return {"runs": []}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"runs": []}


def update_radar_history(workspace_root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    history = load_radar_history(workspace_root)
    runs = history.setdefault("runs", [])
    candidates = payload.get("candidates", [])
    runs.append(
        {
            "generated_at": payload["generated_at"],
            "day": _day_bucket(),
            "trigger_source": payload.get("trigger_source"),
            "candidate_count": payload.get("candidates_count", len(candidates)),
            "real_candidate_count": sum(1 for item in candidates if classify_candidate(item)),
            "all_fields_present": all(
                bool(item.get("source"))
                and bool(item.get("timestamp"))
                and bool(item.get("next_action"))
                for item in candidates
            ),
            "archive_path": payload.get("archive_path"),
            "db_path": payload.get("db_path"),
        }
    )
    runs.sort(key=lambda item: str(item.get("generated_at", "")))
    history["runs"] = runs
    history["summary"] = {
        "run_count": len(runs),
        "cron_run_count": sum(1 for item in runs if item.get("trigger_source") == "cron"),
        "manual_run_count": sum(1 for item in runs if item.get("trigger_source") == "manual"),
        "latest_generated_at": runs[-1]["generated_at"] if runs else None,
        "latest_archive_path": runs[-1]["archive_path"] if runs else None,
        "latest_day": runs[-1]["day"] if runs else None,
    }
    write_text_atomic(
        _history_path(workspace_root),
        json.dumps(history, ensure_ascii=False, indent=2) + "\n",
    )
    return history


def write_radar_snapshot(
    workspace_root: Path, payload: dict[str, Any], history: dict[str, Any]
) -> Path:
    out_dir = workspace_root / ".omo" / "_control" / "evolution" / "radar"
    out_path = out_dir / f"{_day_bucket()}.json"
    snapshot = {
        "generated_at": payload["generated_at"],
        "trigger_source": payload.get("trigger_source"),
        "candidate_count": payload.get("candidates_count", 0),
        "real_candidate_count": sum(
            1 for item in payload.get("candidates", []) if classify_candidate(item)
        ),
        "archive_path": payload.get("archive_path"),
        "history": history.get("summary", {}),
    }
    write_text_atomic(
        out_path,
        json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n",
    )
    return out_path
