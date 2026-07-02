from __future__ import annotations

import json
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .omo_io import write_text_atomic
from .omo_ingress_paths import _retrospective_dir
from .omo_shared import load_yaml


def release_index_path(workspace_root: Path) -> Path:
    return workspace_root / "runtime" / "omo" / "_delivery" / "release" / "index.json"


def load_release_index(workspace_root: Path) -> dict[str, Any]:
    path = release_index_path(workspace_root)
    if not path.exists():
        return {"releases": []}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"releases": []}


def next_release_version(workspace_root: Path, today: str) -> str:
    index = load_release_index(workspace_root)
    todays = [
        item
        for item in index.get("releases", [])
        if str(item.get("version", "")).startswith(f"v{today}-r")
    ]
    return f"v{today}-r{len(todays) + 1}"


def update_release_index(workspace_root: Path, cycle: dict[str, Any]) -> dict[str, Any]:
    index = load_release_index(workspace_root)
    releases = [
        item
        for item in index.get("releases", [])
        if item.get("version") != cycle["version"]
    ]
    latest_existing = releases[-1] if releases else None
    interval_days: int | None = None
    if latest_existing and latest_existing.get("generated_at"):
        try:
            current_dt = datetime.strptime(
                cycle["generated_at"], "%Y-%m-%dT%H:%M:%SZ"
            ).replace(tzinfo=UTC)
            previous_dt = datetime.strptime(
                str(latest_existing["generated_at"]), "%Y-%m-%dT%H:%M:%SZ"
            ).replace(tzinfo=UTC)
            interval_days = (current_dt - previous_dt).days
        except ValueError:
            interval_days = None
    releases.append(
        {
            "version": cycle["version"],
            "generated_at": cycle["generated_at"],
            "trigger_source": cycle.get("trigger_source"),
            "changes_cutoff": cycle["changes"]["cutoff"],
            "commit_count": cycle["changes"]["commit_count"],
            "drift_count": cycle["validation"].get("drift", {}).get("drift_count"),
            "debt_open": cycle["debt"]["open"],
            "interval_days_from_previous": interval_days,
            "cycle_json_path": cycle["cycle_json_path"],
            "retro_path": cycle["retro_path"],
        }
    )
    releases.sort(key=lambda item: str(item["generated_at"]))
    cadence_intervals = [
        item["interval_days_from_previous"]
        for item in releases
        if item.get("interval_days_from_previous") is not None
    ]
    index["releases"] = releases
    index["summary"] = {
        "release_count": len(releases),
        "latest_version": releases[-1]["version"] if releases else None,
        "cron_run_count": sum(
            1 for item in releases if item.get("trigger_source") == "cron"
        ),
        "manual_run_count": sum(
            1 for item in releases if item.get("trigger_source") == "manual"
        ),
        "latest_interval_days": cadence_intervals[-1] if cadence_intervals else None,
        "min_interval_days": min(cadence_intervals) if cadence_intervals else None,
        "max_interval_days": max(cadence_intervals) if cadence_intervals else None,
    }
    write_text_atomic(
        release_index_path(workspace_root),
        json.dumps(index, ensure_ascii=False, indent=2) + "\n",
    )
    return index


def utc_now_iso() -> str:
    override = os.environ.get("OPC_GENERATED_AT", "").strip()
    if override:
        return override
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def utc_today() -> str:
    override = os.environ.get("OPC_TODAY", "").strip()
    if override:
        return override
    return datetime.now(UTC).strftime("%Y-%m-%d")


def trigger_source() -> str:
    return os.environ.get("OPC_TRIGGER", "manual")


def gather_changes(
    workspace_root: Path, *, cutoff: str | None = None
) -> dict[str, Any]:
    index = load_release_index(workspace_root)
    previous_release = index.get("releases", [])[-1] if index.get("releases") else None
    effective_cutoff = cutoff or os.environ.get(
        "OPC_RELEASE_CUTOFF",
        str(previous_release.get("generated_at")) if previous_release else "7 days ago",
    )
    result = subprocess.run(
        [
            "git",
            "log",
            f"--since={effective_cutoff}",
            "--oneline",
            "--no-merges",
        ],
        cwd=str(workspace_root),
        capture_output=True,
        text=True,
    )
    commits = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    return {
        "cutoff": effective_cutoff,
        "commit_count": len(commits),
        "commits": commits[:50],
        "previous_release_version": previous_release.get("version")
        if previous_release
        else None,
    }


def gather_validation(workspace_root: Path) -> dict[str, Any]:
    out: dict[str, Any] = {}
    omo_test = subprocess.run(
        [
            "python3",
            "-m",
            "pytest",
            "projects/omo/tests/test_opc_phase_governance_alignment.py",
            "-q",
        ],
        cwd=str(workspace_root),
        capture_output=True,
        text=True,
    )
    out["omo_tests"] = {
        "returncode": omo_test.returncode,
        "summary": omo_test.stdout.strip().splitlines()[-1] if omo_test.stdout else "",
    }
    drift_test = subprocess.run(
        ["python3", "scripts/opc_p6_drift_detector.py"],
        cwd=str(workspace_root),
        capture_output=True,
        text=True,
    )
    try:
        drift_payload = json.loads(drift_test.stdout.strip())
        out["drift"] = {
            "kinds": drift_payload.get("kinds"),
            "drift_count": drift_payload.get("drift_count"),
        }
    except json.JSONDecodeError:
        out["drift"] = {"error": "drift parse fail"}
    return out


def gather_debt(workspace_root: Path) -> dict[str, Any]:
    debt_dir = workspace_root / ".omo" / "debt" / "items"
    if not debt_dir.exists():
        return {"total": 0, "open": 0, "resolved": 0}
    items: list[dict[str, Any]] = []
    for debt_file in debt_dir.glob("*.yaml"):
        try:
            payload = load_yaml(debt_file)
            items.append(
                {"file": debt_file.name, "status": payload.get("status", "unknown")}
            )
        except Exception:  # noqa: BLE001  # defensive fallback
            items.append({"file": debt_file.name, "status": "parse-fail"})
    total = len(items)
    open_count = sum(1 for item in items if item["status"] == "open")
    return {"total": total, "open": open_count, "resolved": total - open_count}


def write_release_notes(
    workspace_root: Path, version: str, cycle: dict[str, Any]
) -> Path:
    notes_path = workspace_root / "runtime" / "omo" / "_delivery" / "release" / "CHANGELOG.md"
    changes = cycle["changes"]
    validation = cycle["validation"]
    debt = cycle["debt"]

    summary = f"## {version} ({cycle['generated_at']})\n\n"
    summary += "### Summary\n"
    summary += f"- {changes['commit_count']} commits since {changes['cutoff']}\n"
    summary += (
        f"- Drift kinds scanned: {validation.get('drift', {}).get('kinds', '?')}, "
        f"drift_count: {validation.get('drift', {}).get('drift_count', '?')}\n"
    )
    summary += f"- Debt: total={debt['total']}, open={debt['open']}, resolved={debt['resolved']}\n\n"
    summary += "### Validation\n"
    summary += (
        f"- omo tests: rc={validation['omo_tests']['returncode']} | "
        f"{validation['omo_tests']['summary']}\n"
    )
    summary += f"- drift detector: {validation.get('drift', {})}\n\n"
    summary += "### Debt\n"
    summary += f"- total: {debt['total']}\n"
    summary += f"- open: {debt['open']}\n"
    summary += f"- resolved: {debt['resolved']}\n\n"
    summary += "### Commits\n"
    for commit in changes["commits"][:10]:
        summary += f"- {commit}\n"
    summary += "\n"

    existing = (
        notes_path.read_text(encoding="utf-8")
        if notes_path.exists()
        else "# OPC Release Notes\n\n"
    )
    write_text_atomic(notes_path, existing + summary)
    return notes_path


def write_cycle_json(workspace_root: Path, version: str, cycle: dict[str, Any]) -> Path:
    out_dir = workspace_root / "runtime" / "omo" / "_delivery" / "release"
    out_path = out_dir / f"{version}.json"
    write_text_atomic(out_path, json.dumps(cycle, ensure_ascii=False, indent=2) + "\n")
    return out_path


def write_retrospective(
    workspace_root: Path, version: str, cycle: dict[str, Any]
) -> Path:
    retro_dir = _retrospective_dir("OPC-P7-H1", workspace_root)
    retro_path = retro_dir / f"retrospective-{version}.md"
    lines: list[str] = []
    lines.append(f"# OPC P7-H1 retrospective — {version}")
    lines.append("")
    lines.append(f"Generated: {cycle['generated_at']}")
    lines.append("")
    lines.append("## cycle state")
    lines.append(f"- stage: {cycle['stage']}")
    lines.append(f"- version: {version}")
    lines.append(f"- notes: {cycle.get('notes_path', '?')}")
    lines.append("")
    lines.append("## 3 字段 (summary/validation/debt)")
    lines.append("```json")
    lines.append(
        json.dumps(
            {
                "summary": {
                    "commit_count": cycle["changes"]["commit_count"],
                    "drift_count": cycle["validation"]
                    .get("drift", {})
                    .get("drift_count"),
                },
                "validation": cycle["validation"],
                "debt": cycle["debt"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    lines.append("```")
    lines.append("")
    lines.append("## next-action")
    lines.append("- 下一周继续 release cycle")
    lines.append("- 若 drift > 0 触发 self-evolve register")
    lines.append("- H2/H3/H4/H5 同步推进")
    write_text_atomic(retro_path, "\n".join(lines) + "\n")
    return retro_path


def run_release_cycle(
    workspace_root: Path,
    *,
    version: str | None = None,
    today: str | None = None,
    generated_at: str | None = None,
    trigger: str | None = None,
    gather_changes_fn: Any | None = None,
    gather_validation_fn: Any | None = None,
    gather_debt_fn: Any | None = None,
) -> dict[str, Any]:
    effective_today = today or utc_today()
    effective_version = version or next_release_version(workspace_root, effective_today)
    effective_generated_at = generated_at or utc_now_iso()
    effective_trigger = trigger or trigger_source()
    gather_changes_impl = gather_changes_fn or (lambda: gather_changes(workspace_root))
    gather_validation_impl = gather_validation_fn or (
        lambda: gather_validation(workspace_root)
    )
    gather_debt_impl = gather_debt_fn or (lambda: gather_debt(workspace_root))
    cycle: dict[str, Any] = {
        "version": effective_version,
        "stage": "ship",
        "generated_at": effective_generated_at,
        "trigger_source": effective_trigger,
        "cutoff": os.environ.get("OPC_RELEASE_CUTOFF", "7 days ago"),
        "changes": gather_changes_impl(),
        "validation": gather_validation_impl(),
        "debt": gather_debt_impl(),
    }
    cycle["notes_path"] = str(
        write_release_notes(workspace_root, effective_version, cycle).relative_to(
            workspace_root
        )
    )
    cycle["cycle_json_path"] = str(
        write_cycle_json(workspace_root, effective_version, cycle).relative_to(
            workspace_root
        )
    )
    cycle["retro_path"] = str(
        write_retrospective(workspace_root, effective_version, cycle).relative_to(
            workspace_root
        )
    )
    cycle["release_index"] = update_release_index(workspace_root, cycle)
    return cycle
