"""Regression guard for the Architecture Check workflow checkout contract."""

from __future__ import annotations

import shlex
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "architecture-check.yml"


def test_architecture_job_initializes_ecos_before_gate() -> None:
    data = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    steps = data["jobs"]["architecture"]["steps"]

    checkout_index, checkout_step = next(
        (i, step) for i, step in enumerate(steps) if step.get("uses") == "actions/checkout@v4"
    )
    init_index, init_step = next(
        (i, step) for i, step in enumerate(steps) if step.get("name") == "Initialize architecture check consumers"
    )
    gate_index = next(
        i
        for i, step in enumerate(steps)
        if step.get("run") == "python3 bin/gac/architecture-check.py --gate"
    )

    assert checkout_index < init_index < gate_index
    assert checkout_step["with"] == {
        "submodules": False,
        "token": "${{ secrets.CROSS_REPO_TOKEN }}",
    }
    assert init_step["env"] == {
        "CROSS_REPO_TOKEN": "${{ secrets.CROSS_REPO_TOKEN }}",
    }
    script = init_step["run"]
    assert "x-access-token:%s" in script
    assert "http.https://github.com/.extraheader" in script
    assert "https://x-access-token:" not in script
    command_line = next(line.strip() for line in script.splitlines() if "submodule update --init" in line)
    command = shlex.split(command_line)
    submodule_index = command.index("submodule")
    assert command[submodule_index : submodule_index + 3] == ["submodule", "update", "--init"]
    assert set(command[submodule_index + 3 :]) == {
        "projects/ecos",
        "projects/cockpit",
        "projects/family-hub",
        "projects/aetherforge",
        "projects/omlxc",
        "projects/runtime",
        "projects/metaos",
    }
