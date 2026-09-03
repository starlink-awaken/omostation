"""Regression tests for the merge-admission contract of gac-gate."""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def _workflow() -> dict:
    # PyYAML parses the YAML 1.1 boolean key ``on`` as True; normalize it so
    # the test remains explicit about the workflow document's structure.
    raw = yaml.safe_load((ROOT / ".github" / "workflows" / "gac-gate.yml").read_text())
    return raw if "jobs" in raw else raw[True] | {"jobs": raw["jobs"]}


def test_strict_gate_step_is_blocking() -> None:
    steps = _workflow()["jobs"]["gac-gate"]["steps"]
    strict_steps = [step for step in steps if step.get("name") == "gac-local-gate (strict)"]

    assert len(strict_steps) == 1
    assert strict_steps[0].get("continue-on-error", False) is False
