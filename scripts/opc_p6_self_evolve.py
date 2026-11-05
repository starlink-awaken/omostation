#!/usr/bin/env python3
"""OPC P6 self-evolve: read drift detector report and emit OMO planned task packets.

Pipeline:
  1. Locate the latest drift detector report under
     <workspace>/runtime/omo/_control/evolution/drift/
  2. If no report exists, run the built-in drift detector (opc_p6_drift_detector)
     inline to produce one.
  3. Convert each drift item to an OMO planned task packet via
     omo.omo_self_evolve.write_planned_self_evolution_tasks.
  4. All emitted tasks carry approval_required: true (P6 §6.2: self-evolution
     tasks may enter planned state only; human approval required for active).

Exit code: 0. Prints a JSON summary with task count + titles.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Make `omo` package importable when run as `python scripts/opc_p6_self_evolve.py`.
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "projects" / "omo" / "src"))

from omo.omo_ingress_paths import _drift_dir, _self_evolve_dir  # noqa: E402
from omo.omo_self_evolve import (  # noqa: E402
    write_planned_self_evolution_tasks,
    write_self_evolution_summary,
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _latest_drift_report(workspace_root: Path) -> Path | None:
    drift_dir = _drift_dir(workspace_root)
    if not drift_dir.exists():
        return None
    reports = sorted(drift_dir.glob("*.json"))
    return reports[-1] if reports else None


def _run_drift_detector(workspace_root: Path) -> Path:
    """Run the built-in drift detector and return its report path.

    Falls back to an empty report if the detector cannot be imported so the
    self-evolve pipeline never crashes on a missing detector.
    """
    try:
        from opc_p6_drift_detector import detect_drifts  # type: ignore
    except ImportError:
        detect_drifts = None  # type: ignore

    drift_dir = _drift_dir(workspace_root)
    drift_dir.mkdir(parents=True, exist_ok=True)
    now = _utc_now()
    report_path = drift_dir / f"{now[:10]}.json"

    if detect_drifts is None:
        payload = {
            "kinds": 0,
            "drift_count": 0,
            "results": [],
            "note": "drift detector not importable; emitting empty report",
        }
    else:
        payload = detect_drifts(workspace_root)

    report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report_path


def _drift_to_task(drift: dict, idx: int) -> dict:
    drift_id = drift.get("id") or f"drift-{idx:03d}"
    title = drift.get("title") or drift.get("kind") or f"Drift {drift_id}"
    severity = drift.get("severity", "low")
    risk_map = {"critical": "L3", "high": "L2", "medium": "L2", "low": "L1"}
    drift_id_clean = drift_id.upper().replace("-", "")[:16]
    return {
        "id": f"OPC-P6-DRIFT-{drift_id_clean}",
        "title": title,
        "source": drift.get("source", "opc-p6-drift-detector"),
        "drift_ref": drift.get("ref") or drift.get("evidence") or "drift://" + str(drift_id),
        "approval_required": True,
        "human_approval_required": True,
        "risk_level": risk_map.get(str(severity).lower(), "L1"),
    }


def main() -> int:
    workspace_root = ROOT
    now = _utc_now()

    report_path = _latest_drift_report(workspace_root)
    if report_path is None:
        report_path = _run_drift_detector(workspace_root)

    report = json.loads(report_path.read_text(encoding="utf-8"))
    results = report.get("results", []) or []

    tasks = [_drift_to_task(d, i) for i, d in enumerate(results)]
    # Deduplicate by id (keep first).
    seen: set[str] = set()
    unique_tasks = [t for t in tasks if not (t["id"] in seen or seen.add(t["id"]))]

    written = write_planned_self_evolution_tasks(
        workspace_root,
        unique_tasks,
        now=now,
        ingress_plane="scripts/opc_p6_self_evolve.py",
    )

    summary = {
        "generated_at": now,
        "drift_report": str(report_path),
        "drift_count": len(results),
        "task_count": len(unique_tasks),
        "tasks": [
            {"id": t["id"], "title": t["title"], "risk_level": t["risk_level"]}
            for t in unique_tasks
        ],
        "written_paths": [str(p) for p in written],
    }
    summary_path = write_self_evolution_summary(workspace_root, summary, generated_at=now)
    summary["summary_path"] = str(summary_path)

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
