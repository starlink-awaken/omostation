#!/usr/bin/env python3
"""Ruff config drift detector — compare subproject ruff configs against baseline."""

from __future__ import annotations

import json
import sys
from pathlib import Path

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore[no-redef]

WORKSPACE = Path(__file__).resolve().parents[2]
REPORT_PATH = WORKSPACE / ".omo/_truth/registry/ruff-config-drift.json"

BASELINE_SELECT = ["E", "F", "W", "I", "N", "UP", "S", "PLE", "RUF100"]
BASELINE_IGNORE = [
    "ASYNC220",
    "ASYNC221",
    "ASYNC230",
    "B004",
    "BLE001",
    "C401",
    "C408",
    "DTZ005",
    "E402",
    "E501",
    "E701",
    "E702",
    "E722",
    "E731",
    "E741",
    "EXE001",
    "F401",
    "F403",
    "F841",
    "I001",
    "N806",
    "N813",
    "N817",
    "N818",
    "N999",
    "PERF402",
    "PLE1205",
    "PLR0402",
    "PLR1704",
    "PLW0602",
    "PLW1510",
    "RUF012",
    "RUF034",
    "RUF059",
    "RUF100",
    "S101",
    "S102",
    "S103",
    "S104",
    "S105",
    "S108",
    "S110",
    "S112",
    "S310",
    "S311",
    "S314",
    "S324",
    "S602",
    "S603",
    "S607",
    "S608",
    "SIM102",
    "SIM115",
    "SIM117",
    "TRY004",
    "UP022",
    "UP035",
    "UP042",
    "UP047",
    "W291",
    "W292",
]


def load_ruff_config(project_dir: Path) -> dict | None:
    """Load ruff config from pyproject.toml using tomllib."""
    pyproject = project_dir / "pyproject.toml"
    if not pyproject.is_file():
        return None
    try:
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
        ruff = data.get("tool", {}).get("ruff", {})
        lint = ruff.get("lint", {})
        config = {}
        if "select" in lint:
            config["select"] = lint["select"]
        if "ignore" in lint:
            config["ignore"] = lint["ignore"]
        return config if config else None
    except Exception:
        return None


def detect_drift() -> dict:
    """Detect ruff config drift across subprojects."""
    projects = []
    for p in sorted(WORKSPACE.glob("projects/*")):
        if not p.is_dir():
            continue
        config = load_ruff_config(p)
        if config is None:
            projects.append({
                "project": p.name,
                "has_config": False,
                "drift": "missing ruff config",
            })
            continue
        select = config.get("select", [])
        ignore = config.get("ignore", [])
        select_drift = sorted(set(select) - set(BASELINE_SELECT))
        ignore_drift = sorted(set(ignore) - set(BASELINE_IGNORE))
        missing_ignore = sorted(set(BASELINE_IGNORE) - set(ignore))
        projects.append({
            "project": p.name,
            "has_config": True,
            "select_drift": select_drift,
            "ignore_drift": ignore_drift,
            "missing_ignore": missing_ignore,
            "drift_score": len(select_drift),
        })
    return {
        "baseline_select": BASELINE_SELECT,
        "baseline_ignore": BASELINE_IGNORE,
        "projects": projects,
        "total_drift": sum(p.get("drift_score", 0) for p in projects),
    }


def main() -> int:
    report = detect_drift()
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["total_drift"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
