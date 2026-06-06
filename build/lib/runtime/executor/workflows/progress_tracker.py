# ---
# domain: workflows
# layer: tool
# status: active
# ---
"""Structured pipeline progress tracking — timing and structured logging."""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[5]
REPORT_DIR = PROJECT_ROOT / "data" / "planning_results"
TRACKER_FILE = REPORT_DIR / "progress_tracker.json"


@dataclass
class StepTiming:
    step_name: str
    started_at: str = ""
    completed_at: str = ""
    elapsed_ms: float = 0.0
    status: str = "pending"  # pending | running | passed | failed

    def start(self):
        self.started_at = datetime.now(UTC).isoformat()
        self.status = "running"
        self._start = time.monotonic()

    def finish(self, ok: bool):
        self.completed_at = datetime.now(UTC).isoformat()
        self.elapsed_ms = (time.monotonic() - self._start) * 1000
        self.status = "passed" if ok else "failed"


@dataclass
class PipelineRun:
    run_id: str
    goal: str
    steps: list[StepTiming] = field(default_factory=list)
    started_at: str = ""
    completed_at: str = ""
    total_elapsed_ms: float = 0.0
    all_passed: bool = False

    def start(self):
        self.started_at = datetime.now(UTC).isoformat()
        self._start = time.monotonic()

    def finish(self):
        self.completed_at = datetime.now(UTC).isoformat()
        self.total_elapsed_ms = (time.monotonic() - self._start) * 1000
        self.all_passed = all(s.status == "passed" for s in self.steps)

    def summary(self) -> str:
        status_icon = "✅" if self.all_passed else "⚠️"
        step_summary = ", ".join(
            f"{s.step_name}:{s.elapsed_ms:.0f}ms"
            for s in self.steps
            if s.elapsed_ms > 0
        )
        return (
            f"{status_icon} [{self.total_elapsed_ms:.0f}ms] {self.goal[:40]} | {step_summary}"
        )


def create_run(run_id: str, goal: str, step_names: list[str]) -> PipelineRun:
    run = PipelineRun(run_id=run_id, goal=goal)
    run.steps = [StepTiming(step_name=sn) for sn in step_names]
    run.start()
    return run


def save_run(run: PipelineRun):
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    runs = []
    if TRACKER_FILE.exists():
        try:
            runs = json.loads(TRACKER_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass

    entry = asdict(run)
    entry.pop("_start", None)
    for s in entry.get("steps", []):
        s.pop("_start", None)

    runs.append(entry)
    if len(runs) > 50:
        runs = runs[-50:]

    TRACKER_FILE.write_text(
        json.dumps(runs, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def get_recent_runs(limit: int = 10) -> list[dict]:
    if not TRACKER_FILE.exists():
        return []
    try:
        runs = json.loads(TRACKER_FILE.read_text(encoding="utf-8"))
        return runs[-limit:]
    except (json.JSONDecodeError, OSError):
        return []
