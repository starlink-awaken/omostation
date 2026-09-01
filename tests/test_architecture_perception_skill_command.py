from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / ".agents/skills/architecture-perception/SKILL.md"
SCENE_CLI = ROOT / "bin/ssot/scene-card-lifecycle.py"
EXPECTED_COMMAND = (
    'uv run --with pyyaml python "bin/ssot/scene-card-lifecycle.py" '
    "validate --all"
)
STALE_COMMAND = "python3 bin/ssot/scene-card-lifecycle.py --validate --all"


def test_skill_uses_managed_current_scene_validation_command() -> None:
    text = SKILL.read_text(encoding="utf-8")
    assert text.count(EXPECTED_COMMAND) == 1
    assert STALE_COMMAND not in text


def test_scene_validation_cli_exposes_validate_all() -> None:
    completed = subprocess.run(
        [sys.executable, str(SCENE_CLI), "validate", "--help"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "--all" in completed.stdout
