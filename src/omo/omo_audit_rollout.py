from __future__ import annotations

import fcntl
import json
from pathlib import Path
from typing import Any

from .omo_ingress_paths import _drift_history_dir, _runtime_omo_root
from .omo_io import ensure_parent_dir, write_text_atomic


def history_index_path(workspace_root: Path) -> Path:
    return (
        _runtime_omo_root(workspace_root) / "_delivery" / "audit-rollout" / "index.json"
    )


def _locked_write_json(path: Path, payload: dict[str, Any]) -> None:
    ensure_parent_dir(path)
    lock_path = path.with_suffix(path.suffix + ".lock")
    lock_handle = open(lock_path, "w", encoding="utf-8")
    try:
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
        try:
            write_text_atomic(
                path,
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            )
        finally:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)
    finally:
        lock_handle.close()


def load_history_index(workspace_root: Path) -> dict[str, Any]:
    path = history_index_path(workspace_root)
    if not path.exists():
        return {"runs": []}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"runs": []}


def write_drift_history(
    workspace_root: Path,
    mode: str,
    rollout: dict[str, Any],
    generated_at: str,
    today: str,
) -> Path:
    out_dir = _drift_history_dir(workspace_root)
    out_path = out_dir / f"{today}.json"
    summary = {
        "generated_at": generated_at,
        "mode": mode,
        "rollout": {
            "returncode": rollout.get("returncode"),
            "fallback_used": rollout.get("fallback_used"),
            "output_path": rollout.get("output_path"),
        },
    }
    payload = rollout.get("payload")
    if isinstance(payload, dict) and "repos" in payload:
        repos = payload["repos"]
        summary["per_repo"] = {
            name: {
                "health_grade": data.get("health_grade"),
                "drift": data.get("total_drift"),
                "records": data.get("total_records"),
            }
            for name, data in repos.items()
        }
    _locked_write_json(out_path, summary)
    return out_path


def update_history_index(
    workspace_root: Path,
    mode: str,
    rollout: dict[str, Any],
    history_path: Path,
    generated_at: str,
    today: str,
    trigger_source: str,
) -> dict[str, Any]:
    path = history_index_path(workspace_root)
    ensure_parent_dir(path)
    lock_path = path.with_suffix(".lock")
    lock_handle = open(lock_path, "w", encoding="utf-8")
    try:
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
        try:
            if path.exists():
                try:
                    index = json.loads(path.read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    index = {"runs": []}
            else:
                index = {"runs": []}
            runs = index.setdefault("runs", [])
            payload = (
                rollout.get("payload")
                if isinstance(rollout.get("payload"), dict)
                else {}
            )
            repos = payload.get("repos", {}) if isinstance(payload, dict) else {}
            run_entry: dict[str, Any] = {
                "generated_at": generated_at,
                "day": today,
                "mode": mode,
                "trigger_source": trigger_source,
                "returncode": rollout.get("returncode"),
                "fallback_used": rollout.get("fallback_used"),
                "primary_returncode": rollout.get("primary_returncode"),
                "fallback_returncode": rollout.get("fallback_returncode"),
                "output_path": rollout.get("output_path"),
                "primary_output_path": rollout.get("primary_output_path"),
                "fallback_output_path": rollout.get("fallback_output_path"),
                "primary_error": rollout.get("primary_error"),
                "repo_count": len(repos) if isinstance(repos, dict) else 0,
                "history_path": str(history_path.relative_to(workspace_root)),
            }
            if rollout.get("fallback_error"):
                run_entry["fallback_error"] = rollout["fallback_error"]
            runs.append(run_entry)
            runs.sort(key=lambda item: str(item.get("generated_at", "")))
            index["runs"] = runs
            index["summary"] = {  # type: ignore[reportArgumentType]
                "run_count": len(runs),
                "weekly_runs": sum(1 for item in runs if item.get("mode") == "weekly"),
                "monthly_runs": sum(
                    1 for item in runs if item.get("mode") == "monthly"
                ),
                "pre_release_runs": sum(
                    1 for item in runs if item.get("mode") == "pre-release"
                ),
                "cron_run_count": sum(
                    1 for item in runs if item.get("trigger_source") == "cron"
                ),
                "manual_run_count": sum(
                    1 for item in runs if item.get("trigger_source") == "manual"
                ),
                "fallback_used_count": sum(
                    1 for item in runs if item.get("fallback_used")
                ),
                "failed_count": sum(
                    1 for item in runs if item.get("returncode") not in (0, None)
                ),
                "latest_output_path": runs[-1]["output_path"] if runs else None,
                "latest_trigger_source": runs[-1]["trigger_source"] if runs else None,
            }
            write_text_atomic(
                path, json.dumps(index, ensure_ascii=False, indent=2) + "\n"
            )
        finally:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)
    finally:
        lock_handle.close()
    return index


def write_daemon_summary(
    workspace_root: Path,
    mode: str,
    summary: dict[str, Any],
    today: str,
) -> Path:
    out_dir = _runtime_omo_root(workspace_root) / "_delivery" / "audit-rollout"
    summary_path = out_dir / f"{today}-{mode}-daemon-summary.json"
    _locked_write_json(summary_path, summary)
    return summary_path


def main(argv: list[str] | None = None) -> int:
    """omo cli audit-rollout 入口 — 调 scripts/opc_audit_rollout_5repos.py 聚合.

    本模块提供 history helpers (write_drift_history/update_history_index/write_daemon_summary);
    跨仓 baseline 聚合逻辑在 scripts/opc_audit_rollout_5repos.py.
    本 main 是 cli 薄包装, 复用 5repos 聚合 (不重复造轮, DRY).
    """
    import subprocess
    import sys

    workspace_root = Path(__file__).resolve().parents[4]
    script = workspace_root / "scripts" / "opc_audit_rollout_5repos.py"
    if not script.exists():
        print(
            f"❌ {script} 不存在 (audit-rollout 5repos 聚合脚本缺失)",
            file=sys.stderr,
        )
        return 1
    cmd = [sys.executable, str(script)] + (argv or [])
    return subprocess.call(cmd, cwd=str(workspace_root))
