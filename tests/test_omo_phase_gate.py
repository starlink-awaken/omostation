from __future__ import annotations

import json
from pathlib import Path

from omo.omo_phase_gate import write_phase_gate_audit


def test_phase_gate_helper_writes_json_and_md(tmp_path: Path) -> None:
    payload = {
        "generated_at": "2026-06-20T00:00:00Z",
        "summary": {"phases_total": 2, "phases_passed": 1, "phases_open": 1},
        "rows": [
            {
                "phase": "P0",
                "gate": "Gate A",
                "gate_status": "passed",
                "sub_gate_passed": 1,
                "sub_gate_count": 1,
                "sub_gate_open": 0,
            },
            {
                "phase": "P1",
                "gate": "Gate B",
                "gate_status": "not_yet_passed",
                "sub_gate_passed": 0,
                "sub_gate_count": 2,
                "sub_gate_open": 2,
            },
        ],
    }
    json_path, md_path = write_phase_gate_audit(tmp_path, payload, "2026-06-20")

    assert (
        json.loads(json_path.read_text(encoding="utf-8"))["summary"]["phases_total"]
        == 2
    )
    assert md_path.exists()
