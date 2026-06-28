from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .omo_io import write_text_atomic


def _week_sort_key(week: str) -> tuple[int, int]:
    year, week_num = week.split("-W", 1)
    return int(year), int(week_num)


def utc_now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def week_id(date: datetime | None = None) -> str:
    d = date or datetime.now(UTC)
    iso = d.isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


def loop_history_path(workspace_root: Path) -> Path:
    return workspace_root / ".omo" / "_control" / "evolution" / "loop" / "history.json"


def trace_index_path(workspace_root: Path) -> Path:
    return (
        workspace_root / ".omo" / "_control" / "evolution" / "loop" / "trace-index.json"
    )


def load_loop_history(workspace_root: Path) -> dict[str, Any]:
    path = loop_history_path(workspace_root)
    if not path.exists():
        return {"runs": []}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"runs": []}


def consecutive_weeks(runs: list[dict[str, Any]]) -> int:
    weeks = sorted(
        {str(run.get("week")) for run in runs if run.get("week")},
        key=_week_sort_key,
    )
    if not weeks:
        return 0
    streak = 1
    best = 1
    prev_year, prev_week = _week_sort_key(weeks[0])
    for week in weeks[1:]:
        year, week_num = _week_sort_key(week)
        expected_year, expected_week = prev_year, prev_week + 1
        if expected_week > 53:
            expected_year += 1
            expected_week = 1
        if (year, week_num) == (expected_year, expected_week):
            streak += 1
            best = max(best, streak)
        else:
            streak = 1
        prev_year, prev_week = year, week_num
    return best


def update_loop_history(
    workspace_root: Path, payload: dict[str, Any]
) -> dict[str, Any]:
    history = load_loop_history(workspace_root)
    runs = history.setdefault("runs", [])
    runs = [run for run in runs if run.get("week") != payload["week"]]
    runs.append(
        {
            "week": payload["week"],
            "generated_at": payload["generated_at"],
            "candidate_count": payload["gap"].get("candidates_count", 0),
            "planned_count": len(payload["task"].get("planned", [])),
            "drift_count": payload["drift"].get("drift_count", 0),
            "approval_required_all": all(
                item.get("approval_required") is True
                for item in payload["task"].get("planned", [])
            ),
        }
    )
    runs.sort(key=lambda item: _week_sort_key(str(item["week"])))
    history["runs"] = runs
    history["summary"] = {
        "weeks_recorded": len(runs),
        "max_consecutive_weeks": consecutive_weeks(runs),
        "latest_week": runs[-1]["week"] if runs else None,
    }
    write_text_atomic(
        loop_history_path(workspace_root),
        json.dumps(history, ensure_ascii=False, indent=2) + "\n",
    )
    return history


def update_trace_index(
    workspace_root: Path,
    payload: dict[str, Any],
    weekly_md_path: Path,
    weekly_json_path: Path,
) -> dict[str, Any]:
    path = trace_index_path(workspace_root)
    if path.exists():
        try:
            index = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            index = {"weeks": []}
    else:
        index = {"weeks": []}
    weeks = [
        item for item in index.get("weeks", []) if item.get("week") != payload["week"]
    ]
    weeks.append(
        {
            "week": payload["week"],
            "generated_at": payload["generated_at"],
            "radar_archive_path": payload["radar"]["output"].get("archive_path"),
            "weekly_json_path": str(weekly_json_path.relative_to(workspace_root)),
            "weekly_md_path": str(weekly_md_path.relative_to(workspace_root)),
            "planned_task_ids": [
                item["id"] for item in payload["task"].get("planned", [])
            ],
            "approval_lane": payload["swarm"].get("approval_lane"),
            "drift_count": payload["drift"].get("drift_count", 0),
        }
    )
    weeks.sort(key=lambda item: str(item.get("generated_at", "")))
    index["weeks"] = weeks
    index["summary"] = {
        "week_count": len(weeks),
        "latest_week": weeks[-1]["week"] if weeks else None,
        "latest_radar_archive_path": weeks[-1]["radar_archive_path"] if weeks else None,
    }
    write_text_atomic(path, json.dumps(index, ensure_ascii=False, indent=2) + "\n")
    return index


def write_weekly_markdown(md_path: Path, payload: dict[str, Any]) -> None:
    lines: list[str] = []
    lines.append(f"# OPC P6 weekly retro — {payload['week']}")
    lines.append("")
    lines.append(f"Generated: {payload['generated_at']}")
    lines.append("")
    lines.append("## 1. Radar (P5-F1)")
    for c in payload["radar"]["output"].get("candidates", []):
        lines.append(f"- **{c.get('title')}**")
        lines.append(f"  - source: `{c.get('source')}`")
        lines.append(f"  - timestamp: `{c.get('timestamp')}`")
        lines.append(f"  - next_action: {c.get('next_action')}")
        if c.get("evidence_id"):
            lines.append(f"  - evidence_id: {c['evidence_id']}")
    lines.append("")
    lines.append("## 2. Drift detector (P6-G3)")
    lines.append(f"- kinds: {payload['drift'].get('kinds', 0)}")
    lines.append(f"- drift_count: **{payload['drift'].get('drift_count', 0)}**")
    for r in payload["drift"].get("results", []):
        marker = "DRIFT" if r.get("drift") else "ok"
        lines.append(f"  - `{r['kind']}` → {marker}")
    lines.append("")
    lines.append("## 3. Gap → top candidates (sorted)")
    for i, c in enumerate(payload["gap"].get("candidates", []), start=1):
        lines.append(
            f"{i}. score={c.get('score')} lane={c.get('lane')} title={c['candidate'].get('title')}"
        )
    lines.append("")
    lines.append("## 4. Task (planned, 人工审批)")
    for t in payload["task"].get("planned", []):
        lines.append(
            f"- `{t['id']}` | {t.get('title')} | approval_required={t.get('approval_required')}"
        )
    lines.append("")
    lines.append("## 5. Swarm (派发受红线约束)")
    lines.append(f"- planned_dispatch: {payload['swarm'].get('planned_dispatch', [])}")
    lines.append(f"- note: {payload['swarm'].get('note')}")
    lines.append("")
    lines.append("## 6. Audit (跨仓 trail)")
    lines.append(
        f"- llm_audit_tail_count: {payload['audit'].get('llm_audit_count', 0)}"
    )
    for line in payload["audit"].get("llm_audit_tail", [])[-3:]:
        lines.append(
            f"  - {line.get('ts')} task_id={line.get('task_id')} role={line.get('role')} cost={line.get('total_cost_usd')}"
        )
    lines.append("")
    lines.append("## 7. Retro / next-action")
    lines.append("```json")
    lines.append(json.dumps(payload["retro"], ensure_ascii=False, indent=2))
    lines.append("```")
    lines.append("")
    lines.append("## 7.5. History / continuity")
    history_summary = payload.get("history", {}).get("summary", {})
    lines.append(f"- weeks_recorded: {history_summary.get('weeks_recorded', 0)}")
    lines.append(
        f"- max_consecutive_weeks: {history_summary.get('max_consecutive_weeks', 0)}"
    )
    lines.append(f"- latest_week: {history_summary.get('latest_week')}")
    lines.append("")
    lines.append("## 8. 人工审批栏")
    lines.append("- [ ] reviewer A: ____  date: ____")
    lines.append("- [ ] reviewer B: ____  date: ____")
    lines.append("")
    lines.append("---")
    lines.append("loop runner: scripts/opc_p6_weekly_loop.py")
    lines.append("drift detector: scripts/opc_p6_drift_detector.py")
    write_text_atomic(md_path, "\n".join(lines) + "\n")


def write_weekly_evidence(
    workspace_root: Path, week: str, payload: dict[str, Any]
) -> tuple[Path, Path]:
    out_dir = workspace_root / ".omo" / "_control" / "evolution" / "loop"
    json_path = out_dir / f"{week}.json"
    write_text_atomic(
        json_path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    )
    md_dir = workspace_root / ".omo" / "tasks" / "registry" / "done" / "OPC-P6-G1"
    md_path = md_dir / f"weekly-{week}.md"
    write_weekly_markdown(md_path, payload)
    update_trace_index(workspace_root, payload, md_path, json_path)
    return md_path, json_path


def write_mof_state_bridge_snapshot(
    workspace_root: Path, payload: dict[str, Any]
) -> Path:
    out_dir = workspace_root / ".omo" / "_delivery" / "audit-rollout"
    stamp = str(payload["generated_at"])
    date = stamp[:10]
    path = out_dir / f"{date}-mof-state-bridge.json"
    write_text_atomic(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    return path


def call_radar(workspace_root: Path) -> dict[str, Any]:
    try:
        scripts_dir = str(workspace_root / "scripts")
        if scripts_dir not in sys.path:
            sys.path.insert(0, scripts_dir)
        from opc_p5_radar_cron import _run_radar  # type: ignore

        prior = os.environ.get("OPC_TRIGGER")
        os.environ["OPC_TRIGGER"] = prior or "loop"
        payload = _run_radar(limit=8)
        if prior is None:
            os.environ.pop("OPC_TRIGGER", None)
        else:
            os.environ["OPC_TRIGGER"] = prior
        return payload
    except Exception as exc:  # noqa: BLE001  # defensive fallback
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                f"import sys; sys.path.insert(0, '{workspace_root}/projects/cockpit/src'); "
                "from cockpit.commands.scenario import _f1_technical_radar; "
                "import json; print(json.dumps(_f1_technical_radar(limit=8), ensure_ascii=False))",
            ],
            cwd=str(workspace_root),
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            return {
                "scenario": "technical-radar",
                "candidates": [],
                "error": f"{exc} | {result.stderr}",
            }
        try:
            return json.loads(result.stdout.strip())
        except json.JSONDecodeError:
            return {
                "scenario": "technical-radar",
                "candidates": [],
                "error": "subprocess parse fail",
            }


def call_drift(workspace_root: Path, *, now_iso: str | None = None) -> dict[str, Any]:
    stamp = now_iso or utc_now_iso()
    drift_path = (
        workspace_root
        / ".omo"
        / "_control"
        / "evolution"
        / "drift"
        / f"{stamp[:10]}.json"
    )
    if drift_path.exists():
        try:
            return json.loads(drift_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    result = subprocess.run(
        [sys.executable, "scripts/opc_p6_drift_detector.py"],
        cwd=str(workspace_root),
        capture_output=True,
        text=True,
    )
    try:
        return json.loads(result.stdout.strip())
    except json.JSONDecodeError:
        return {"kinds": 0, "drift_count": 0, "results": []}


def stage_radar(
    workspace_root: Path,
    *,
    now_iso: str | None = None,
    radar_output: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "stage": "radar",
        "ts": now_iso or utc_now_iso(),
        "output": radar_output or call_radar(workspace_root),
    }


def stage_gap(
    radar: dict[str, Any], drift: dict[str, Any], *, now_iso: str | None = None
) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    for candidate in radar.get("output", {}).get("candidates", []):
        score = 0.0
        if candidate.get("evidence_id"):
            score += 1.0
        if any(
            key in (candidate.get("title") or "").lower()
            for key in ("p4", "p5", "p6", "cockpit", "agora")
        ):
            score += 0.5
        candidates.append({"candidate": candidate, "score": score, "lane": "radar"})

    for result in drift.get("results", []):
        if result.get("drift"):
            candidates.append(
                {
                    "candidate": {
                        "title": f"Fix {result['kind']} drift",
                        "source": f"drift:{result['kind']}",
                        "timestamp": result.get("ts", now_iso or utc_now_iso()),
                        "next_action": f"see drift report: {result['kind']}",
                    },
                    "score": 2.0,
                    "lane": "drift",
                }
            )

    candidates.sort(key=lambda item: item["score"], reverse=True)
    return {
        "stage": "gap",
        "ts": now_iso or utc_now_iso(),
        "candidates": candidates[:10],
        "candidates_count": len(candidates[:10]),
    }


def stage_task(
    gap: dict[str, Any], *, week: str, now_iso: str | None = None
) -> dict[str, Any]:
    planned: list[dict[str, Any]] = []
    stamp = now_iso or utc_now_iso()
    for index, item in enumerate(gap.get("candidates", [])):
        candidate = item["candidate"]
        planned.append(
            {
                "id": f"OPC-P6-LOOP-{week}-{index:02d}",
                "title": candidate.get("title"),
                "source": candidate.get("source"),
                "score": item.get("score"),
                "lane": item.get("lane"),
                "status": "planned",
                "approval_required": True,
                "ts": stamp,
            }
        )
    return {
        "stage": "task",
        "ts": stamp,
        "planned": planned,
        "red_line_held": "all tasks status=planned; human approval required for active",
    }


def stage_swarm(task: dict[str, Any], *, now_iso: str | None = None) -> dict[str, Any]:
    return {
        "stage": "swarm",
        "ts": now_iso or utc_now_iso(),
        "note": "P6 closeout 范围内只 plan; 实际派发受红线 'self-evolution task 仅落 planned' 约束",
        "planned_dispatch": [task_item["id"] for task_item in task.get("planned", [])],
        "approval_lane": "opc-p6-self-evolution-board",
    }


def stage_audit(workspace_root: Path, *, now_iso: str | None = None) -> dict[str, Any]:
    audit_path = (
        workspace_root / "projects" / "llm-gateway" / "audit" / "llm_calls.jsonl"
    )
    audit_lines: list[dict[str, Any]] = []
    if audit_path.exists():
        try:
            for line in audit_path.read_text(encoding="utf-8").splitlines()[-5:]:
                if line.strip():
                    audit_lines.append(json.loads(line))
        except (json.JSONDecodeError, OSError):
            pass
    return {
        "stage": "audit",
        "ts": now_iso or utc_now_iso(),
        "llm_audit_tail": audit_lines,
        "llm_audit_count": len(audit_lines),
    }


def stage_retro(
    loop_payload: dict[str, Any], *, now_iso: str | None = None
) -> dict[str, Any]:
    return {
        "stage": "retro",
        "ts": now_iso or utc_now_iso(),
        "summary": {
            "radar_candidates": len(
                loop_payload["radar"]["output"].get("candidates", [])
            ),
            "radar_archive_path": loop_payload["radar"]["output"].get("archive_path"),
            "drift_count": loop_payload["drift"].get("drift_count", 0),
            "planned_tasks": len(loop_payload["task"]["planned"]),
            "audit_records": loop_payload["audit"]["llm_audit_count"],
            "history_weeks_recorded": loop_payload.get("history", {})
            .get("summary", {})
            .get("weeks_recorded", 0),
            "history_max_consecutive_weeks": loop_payload.get("history", {})
            .get("summary", {})
            .get("max_consecutive_weeks", 0),
        },
        "next_action": "next week's loop continues; if drift > 0 trigger self-evolve register",
        "evidence_complete": True,
    }


def run_weekly_loop(
    workspace_root: Path,
    *,
    week: str | None = None,
    now_iso: str | None = None,
    radar_fn: Any | None = None,
    drift_fn: Any | None = None,
) -> dict[str, Any]:
    effective_week = week or week_id()
    stamp = now_iso or utc_now_iso()
    radar_output = (radar_fn or (lambda: call_radar(workspace_root)))()
    radar = stage_radar(workspace_root, now_iso=stamp, radar_output=radar_output)
    drift = (drift_fn or (lambda: call_drift(workspace_root, now_iso=stamp)))()
    gap = stage_gap(radar, drift, now_iso=stamp)
    task = stage_task(gap, week=effective_week, now_iso=stamp)
    swarm = stage_swarm(task, now_iso=stamp)
    audit = stage_audit(workspace_root, now_iso=stamp)
    payload: dict[str, Any] = {
        "week": effective_week,
        "generated_at": stamp,
        "radar": radar,
        "drift": drift,
        "gap": gap,
        "task": task,
        "swarm": swarm,
        "audit": audit,
    }
    payload["history"] = update_loop_history(workspace_root, payload)
    payload["retro"] = stage_retro(payload, now_iso=stamp)
    return payload


def run_mof_state_bridge_cron_snapshot(workspace_root: Path) -> Path:
    stamp = utc_now_iso()
    result = subprocess.run(
        [
            "python3",
            "projects/ecos/src/ecos/ssot/tools/mof-state-bridge.py",
            "--json",
            "--strict",
        ],
        cwd=str(workspace_root),
        capture_output=True,
        text=True,
        timeout=60,
    )
    in_sync = False
    m1_count = omo_count = paired = drift = m1_only = 0
    if result.returncode == 0:
        try:
            data = json.loads(result.stdout.strip())
            diff = data.get("diff", {})
            m1_count = data.get("m1_count", 0)
            omo_count = data.get("omo_count", 0)
            paired = data.get("paired", 0)
            drift = len(diff.get("drifts", []))
            m1_only = len(diff.get("m1_only", []))
            in_sync = m1_only == 0
        except json.JSONDecodeError:
            pass
    payload_out = {
        "generated_at": stamp,
        "trigger_source": os.environ.get("OPC_TRIGGER", "manual"),
        "mode": os.environ.get("OPC_MODE", "weekly"),
        "source": "opc_p6_weekly_loop",
        "mof_state_bridge": {
            "in_sync": in_sync,
            "m1_count": m1_count,
            "omo_count": omo_count,
            "paired": paired,
            "drift_count": drift,
            "m1_only": m1_only,
            "blocking": not in_sync,
        },
    }
    return write_mof_state_bridge_snapshot(workspace_root, payload_out)
