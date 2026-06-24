from __future__ import annotations

import json
from pathlib import Path

from omo.omo_audit_rollout import (
    update_history_index,
    write_daemon_summary,
    write_drift_history,
)


def test_audit_rollout_helpers_persist_files(tmp_path: Path) -> None:
    rollout = {
        "returncode": 0,
        "fallback_used": True,
        "primary_returncode": 1,
        "fallback_returncode": 0,
        "output_path": ".omo/_delivery/audit-rollout/2026-06-20-5repos.json",
        "primary_output_path": None,
        "fallback_output_path": ".omo/_delivery/audit-rollout/2026-06-20-5repos.json",
        "primary_error": "primary fail",
        "payload": {
            "repos": {
                "workspace": {
                    "health_grade": "R3",
                    "total_drift": 0,
                    "total_records": 4,
                }
            }
        },
    }
    history_path = write_drift_history(
        tmp_path, "weekly", rollout, "2026-06-20T00:00:00Z", "2026-06-20"
    )
    index = update_history_index(
        tmp_path,
        "weekly",
        rollout,
        history_path,
        "2026-06-20T00:00:00Z",
        "2026-06-20",
        "manual",
    )
    summary_path = write_daemon_summary(
        tmp_path,
        "weekly",
        {
            "generated_at": "2026-06-20T00:00:00Z",
            "mode": "weekly",
            "history_summary": index["summary"],
        },
        "2026-06-20",
    )

    assert history_path.exists()
    assert index["summary"]["run_count"] == 1
    assert json.loads(summary_path.read_text(encoding="utf-8"))["mode"] == "weekly"
