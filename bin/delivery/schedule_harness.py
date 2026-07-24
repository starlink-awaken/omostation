#!/usr/bin/env python3
"""STRAT-P81 Batch1 C2 — distributed schedule harness (sim + physical switch).

Cron-friendly daily entry. Physical switch is config-only via env:
  SCHEDULE_HARNESS_MODE=sim|physical
  SCHEDULE_HARNESS_PHYSICAL_ENDPOINTS=host1:port,host2:port
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from agent_registry import AgentRegistry  # noqa: E402
from caliber import ENV_CLASS_SIM  # noqa: E402
from scheduler import measure_schedule_success_rate  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT = ROOT / ".omo" / "_delivery" / "schedule-harness"


def run_sim_batch(*, n_nodes: int = 4, n_tasks: int = 200) -> dict[str, Any]:
    m = measure_schedule_success_rate(
        n_nodes=n_nodes, agents_per_node=2, n_tasks=n_tasks
    )
    m["harness"] = "schedule_harness"
    m["mode"] = "sim"
    m["ts"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    # fail-closed physical fields already set by measure_schedule_success_rate
    assert m.get("meets_physical_gate") is False
    assert m.get("meets_gate") is False
    assert m.get("env_class") == ENV_CLASS_SIM or "sim" in str(m.get("env_class", ""))
    return m


def run_once(*, mode: str | None = None, out_dir: Path | None = None) -> dict[str, Any]:
    mode = (mode or os.environ.get("SCHEDULE_HARNESS_MODE") or "sim").lower()
    out = out_dir or DEFAULT_OUT
    out.mkdir(parents=True, exist_ok=True)
    if mode == "physical":
        # Config-only switch: physical endpoints required; do not claim pass without measure_physical
        endpoints = os.environ.get("SCHEDULE_HARNESS_PHYSICAL_ENDPOINTS", "").strip()
        report = {
            "ok": False,
            "mode": "physical",
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "endpoints": endpoints.split(",") if endpoints else [],
            "error": "physical_mode_requires_measure_physical_and_hosts",
            "meets_sim_harness": False,
            "meets_physical_gate": False,
            "meets_gate": False,
            "env_class": "physical_multi_host",
            "note": "Same harness entry; flip SCHEDULE_HARNESS_MODE without code change",
        }
    else:
        report = run_sim_batch()
        report["ok"] = bool(report.get("meets_sim_harness"))
        report["mode"] = "sim"

    day = time.strftime("%Y-%m-%d", time.gmtime())
    path = out / f"sim-report-{day}.json"
    # append multi-run history as jsonl sibling
    hist = out / f"sim-report-{day}.jsonl"
    with hist.open("a", encoding="utf-8") as f:
        f.write(json.dumps(report, ensure_ascii=False) + "\n")
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    report["report_path"] = str(path)
    report["history_path"] = str(hist)
    return report


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--mode", choices=["sim", "physical"], default=None)
    p.add_argument("--out", type=Path, default=None)
    args = p.parse_args(argv)
    report = run_once(mode=args.mode, out_dir=args.out)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report.get("ok") or report.get("mode") == "physical" else 1


if __name__ == "__main__":
    raise SystemExit(main())
