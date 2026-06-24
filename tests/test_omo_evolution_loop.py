from __future__ import annotations

from pathlib import Path

import omo.omo_evolution_loop as evolution_loop


def test_evolution_loop_run_once_accepts_multi_document_yaml(
    tmp_path: Path, monkeypatch
) -> None:
    debt_dir = tmp_path / ".omo" / "debt" / "items"
    proposal_dir = tmp_path / ".omo" / "state" / "proposals"
    debt_dir.mkdir(parents=True, exist_ok=True)
    proposal_dir.mkdir(parents=True, exist_ok=True)
    (debt_dir / "DEBT-BUDGET-001.yaml").write_text(
        "---\nstatus: active\nowner: governance\n---\n---\n"
        "id: DEBT-BUDGET-001\n"
        "title: Budget exhausted\n"
        "status: open\n"
        "severity: medium\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(evolution_loop, "DEBT_DIR", debt_dir)
    monkeypatch.setattr(evolution_loop, "PROPOSAL_DIR", proposal_dir)

    loop = evolution_loop.EvolutionLoop(interval_sec=1)
    triggered = loop.run_once()

    assert triggered == 1
    assert any(path.name.startswith("PROP-BUDGET-001") for path in proposal_dir.glob("*.yaml"))
