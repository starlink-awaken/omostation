from __future__ import annotations

from pathlib import Path

import yaml
from omo import omo_ledger


def test_omo_ledger_accepts_multi_document_yaml_inputs(
    tmp_path: Path, monkeypatch
) -> None:
    omo_dir = tmp_path / ".omo"
    (omo_dir / "state").mkdir(parents=True, exist_ok=True)
    (omo_dir / "goals").mkdir(parents=True, exist_ok=True)
    (omo_dir / "debt" / "dashboard").mkdir(parents=True, exist_ok=True)
    (omo_dir / "tasks" / "active").mkdir(parents=True, exist_ok=True)
    (omo_dir / "tasks" / "planned").mkdir(parents=True, exist_ok=True)
    (omo_dir / "state" / "system.yaml").write_text(
        "---\nstatus: active\nowner: governance\n---\n---\ncurrent_phase: 46\n",
        encoding="utf-8",
    )
    (omo_dir / "goals" / "current.yaml").write_text(
        "---\nstatus: active\n---\n---\ngoals:\n  - id: G46.1\n    status: pending\n",
        encoding="utf-8",
    )
    (omo_dir / "debt" / "dashboard" / "current.yaml").write_text(
        "---\nstatus: active\n---\n---\nsummary:\n  total: 1\n",
        encoding="utf-8",
    )
    (omo_dir / "tasks" / "active" / "TASK-1.yaml").write_text(
        "id: TASK-1\n", encoding="utf-8"
    )
    (omo_dir / "tasks" / "planned" / "TASK-2.yaml").write_text(
        "id: TASK-2\n", encoding="utf-8"
    )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(omo_ledger, "get_omo_dir", lambda base_dir: omo_dir)
    assert omo_ledger.main(["--message", "multi-doc snapshot"]) == 0

    latest = (
        omo_dir / "_delivery" / "governance-evidence" / "ledgers" / "ledger-latest.yaml"
    )
    payload = yaml.safe_load(latest.read_text(encoding="utf-8"))
    assert payload["system_state"]["current_phase"] == 46
    assert payload["system_state"]["status"] == "active"
    assert payload["goals"]["goals"][0]["id"] == "G46.1"
    assert payload["debt"]["summary"]["total"] == 1
