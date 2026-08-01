from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
SPEC = importlib.util.spec_from_file_location(
    "check_state_goals_alignment",
    ROOT / "scripts/check-state-goals-alignment.py",
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _configure(tmp_path: Path, *, phase: int, wave: str, mode: str, active_tasks: int) -> None:
    omo_dir = tmp_path / ".omo"
    (omo_dir / "state").mkdir(parents=True)
    (omo_dir / "goals").mkdir()
    (omo_dir / "tasks" / "active").mkdir(parents=True)
    (omo_dir / "tasks" / "blocked").mkdir()
    (omo_dir / "tasks" / "done").mkdir()
    (omo_dir / "state/system.yaml").write_text(
        f"current_phase: {phase}\ncurrent_wave: {wave}\nactive_tasks: {active_tasks}\n",
        encoding="utf-8",
    )
    (omo_dir / "goals/current.yaml").write_text(
        f"---\nstatus: active\n---\nphase: {phase}\n"
        f"current_wave: {wave}\nexecution_mode: {mode}\ngoals: []\n",
        encoding="utf-8",
    )
    MODULE.OMO_DIR = omo_dir
    MODULE.SYSTEM_YAML = omo_dir / "state/system.yaml"
    MODULE.GOALS_YAML = omo_dir / "goals/current.yaml"


def test_alignment_accepts_waiting_state(tmp_path: Path) -> None:
    _configure(
        tmp_path,
        phase=47,
        wave="W1",
        mode="waiting-for-scenario/next-bet",
        active_tasks=0,
    )
    assert MODULE.main() == 0


def test_alignment_rejects_phase_wave_mismatch(tmp_path: Path) -> None:
    _configure(
        tmp_path,
        phase=47,
        wave="W1",
        mode="waiting-for-scenario/next-bet",
        active_tasks=0,
    )
    MODULE.GOALS_YAML.write_text(
        "---\nstatus: active\n---\nphase: 46\ncurrent_wave: W6\n"
        "execution_mode: waiting-for-scenario/next-bet\ngoals: []\n",
        encoding="utf-8",
    )
    assert MODULE.main() == 1


def test_alignment_rejects_waiting_mode_with_active_tasks(tmp_path: Path) -> None:
    _configure(
        tmp_path,
        phase=47,
        wave="W1",
        mode="waiting-for-scenario/next-bet",
        active_tasks=1,
    )
    assert MODULE.main() == 1
