"""MOS consolidate — orchestrate gbrain dream (sleep-time), do not reimplement cycle.

ADR-0372 Phase 3 / Letta sleep-time alignment.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

# Default dream phases for memory consolidation (subset of ALL_PHASES)
DEFAULT_CONSOLIDATE_PHASES: tuple[str, ...] = (
    "extract_facts",
    "consolidate",
    "embed",
)


@runtime_checkable
class DreamRunner(Protocol):
    def run(
        self,
        *,
        phases: list[str],
        dry_run: bool,
        json_output: bool,
    ) -> dict[str, Any]: ...


@dataclass
class SubprocessDreamRunner:
    """Invoke `bun run … gbrain dream` when available; degrade cleanly if missing."""

    workspace: Path | None = None
    timeout_sec: float = 600.0

    def _workspace(self) -> Path:
        if self.workspace:
            return self.workspace
        env = os.environ.get("ECOS_WORKSPACE") or os.environ.get("WORKSPACE_ROOT")
        if env:
            return Path(env)
        # .../packages/mos/src/mos/consolidate.py → parents[6] = workspace
        return Path(__file__).resolve().parents[6]

    def run(
        self,
        *,
        phases: list[str],
        dry_run: bool,
        json_output: bool,
    ) -> dict[str, Any]:
        ws = self._workspace()
        gbrain_cli = ws / "projects" / "gbrain" / "src" / "cli.ts"
        bun = shutil.which("bun")
        if not gbrain_cli.is_file():
            return {
                "ok": False,
                "degraded": True,
                "error": f"gbrain cli not found at {gbrain_cli}",
                "phases_requested": phases,
            }
        if not bun:
            return {
                "ok": False,
                "degraded": True,
                "error": "bun not on PATH; cannot run gbrain dream",
                "phases_requested": phases,
            }

        phase_reports: list[dict[str, Any]] = []
        overall_ok = True
        # gbrain dream --phase accepts a single phase; run sequentially
        for phase in phases:
            cmd = [bun, "run", str(gbrain_cli), "dream", "--phase", phase]
            if dry_run:
                cmd.append("--dry-run")
            if json_output:
                cmd.append("--json")
            try:
                proc = subprocess.run(
                    cmd,
                    cwd=str(ws / "projects" / "gbrain"),
                    capture_output=True,
                    text=True,
                    timeout=self.timeout_sec,
                    check=False,
                )
            except subprocess.TimeoutExpired as exc:
                overall_ok = False
                phase_reports.append(
                    {
                        "phase": phase,
                        "ok": False,
                        "error": "timeout",
                        "timeout_sec": self.timeout_sec,
                        "stdout": (exc.stdout or "")[:500] if hasattr(exc, "stdout") else "",
                    }
                )
                continue
            parsed: dict[str, Any] | None = None
            if proc.stdout and proc.stdout.strip():
                try:
                    parsed = json.loads(proc.stdout.strip().splitlines()[-1])
                except json.JSONDecodeError:
                    parsed = {"raw": proc.stdout[-1000:]}
            ok = proc.returncode == 0
            if not ok:
                overall_ok = False
            phase_reports.append(
                {
                    "phase": phase,
                    "ok": ok,
                    "returncode": proc.returncode,
                    "result": parsed,
                    "stderr": (proc.stderr or "")[:400],
                }
            )
        return {
            "ok": overall_ok,
            "degraded": not overall_ok,
            "phases_requested": phases,
            "phase_reports": phase_reports,
            "engine": "gbrain.dream",
            "dry_run": dry_run,
        }


@dataclass
class FakeDreamRunner:
    """Test double — no subprocess."""

    calls: list[dict[str, Any]] = field(default_factory=list)
    fail_phases: set[str] = field(default_factory=set)

    def run(
        self,
        *,
        phases: list[str],
        dry_run: bool,
        json_output: bool,
    ) -> dict[str, Any]:
        self.calls.append({"phases": list(phases), "dry_run": dry_run, "json_output": json_output})
        reports = []
        ok = True
        for p in phases:
            failed = p in self.fail_phases
            if failed:
                ok = False
            reports.append({"phase": p, "ok": not failed, "dry_run": dry_run})
        return {
            "ok": ok,
            "degraded": not ok,
            "phases_requested": phases,
            "phase_reports": reports,
            "engine": "fake.dream",
            "dry_run": dry_run,
        }


@dataclass
class ConsolidateResult:
    ok: bool
    dry_run: bool
    phases: list[str]
    duration_ms: int
    engine_report: dict[str, Any]
    backlog_before: dict[str, Any]
    backlog_after: dict[str, Any]
    degraded: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "dry_run": self.dry_run,
            "phases": self.phases,
            "duration_ms": self.duration_ms,
            "degraded": self.degraded or self.engine_report.get("degraded", False),
            "engine_report": self.engine_report,
            "backlog_before": self.backlog_before,
            "backlog_after": self.backlog_after,
        }


def measure_backlog(theta_docs: list[dict[str, Any]], forgotten: set[str] | None = None) -> dict[str, Any]:
    forgotten = forgotten or set()
    active = [d for d in theta_docs if not d.get("forgotten") and str(d.get("id")) not in forgotten]
    return {
        "theta_docs": len(theta_docs),
        "active_docs": len(active),
        "forgotten": len(forgotten),
    }


def run_consolidate(
    *,
    dream: DreamRunner | None = None,
    phases: list[str] | None = None,
    dry_run: bool = False,
    backlog_before: dict[str, Any] | None = None,
    backlog_after: dict[str, Any] | None = None,
) -> ConsolidateResult:
    """Orchestrate sleep-time consolidation via gbrain dream (or injectable runner)."""
    runner = dream or SubprocessDreamRunner()
    phase_list = list(phases or DEFAULT_CONSOLIDATE_PHASES)
    t0 = time.time()
    report = runner.run(phases=phase_list, dry_run=dry_run, json_output=True)
    duration_ms = int((time.time() - t0) * 1000)
    return ConsolidateResult(
        ok=bool(report.get("ok")),
        dry_run=dry_run,
        phases=phase_list,
        duration_ms=duration_ms,
        engine_report=report,
        backlog_before=backlog_before or {},
        backlog_after=backlog_after or {},
        degraded=bool(report.get("degraded")),
    )
