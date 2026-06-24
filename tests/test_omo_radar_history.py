from __future__ import annotations

import json
from pathlib import Path

from omo.omo_radar_history import update_radar_history, write_radar_snapshot


def test_update_radar_history_and_snapshot(tmp_path: Path) -> None:
    payload = {
        "generated_at": "2026-06-20T00:00:00Z",
        "trigger_source": "manual",
        "candidates_count": 2,
        "archive_path": "/tmp/archive-1.json",
        "db_path": "/tmp/data.db",
        "candidates": [
            {
                "source": "cockpit:research",
                "timestamp": "2026-06-20T00:00:00Z",
                "next_action": "x",
                "evidence_id": 1,
            },
            {
                "source": "cockpit:research (DB unavailable)",
                "timestamp": "2026-06-20T00:00:01Z",
                "next_action": "y",
                "evidence_id": None,
            },
        ],
    }
    history = update_radar_history(tmp_path, payload)
    snapshot_path = write_radar_snapshot(tmp_path, payload, history)

    assert history["summary"]["run_count"] == 1
    assert history["runs"][0]["real_candidate_count"] == 1
    written = json.loads(snapshot_path.read_text(encoding="utf-8"))
    assert written["real_candidate_count"] == 1
