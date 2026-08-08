"""Governed single-run adapter for the approval timeout watchdog.

Mirrors mesh_watchdog_runner.py: one mutually exclusive scan per tick,
durable summary persisted to append-only log + latest JSON.
"""

from __future__ import annotations

import fcntl
import json
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from ._shared.append_only_log import AppendOnlyLog, fcntl_lock
from .approval_lifecycle import ApprovalLifecycleError, scan_approval_timeouts
from .omo_io import write_text_atomic

RUN_SCHEMA = "approval-timeout-runner/v1"
RUN_LOG_NAME = "approval-timeout-runs.jsonl"
RUN_LATEST_NAME = "approval-timeout-latest.json"
RUN_LOCK_NAME = "approval-timeout-run.lock"


def _stamp(value: str | None = None) -> str:
    parsed = datetime.fromisoformat(
        (value or datetime.now(UTC).isoformat()).replace("Z", "+00:00")
    )
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return (
        parsed.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    )


def _paths(omo_dir: Path) -> tuple[Path, Path, Path]:
    log_dir = omo_dir / "_log"
    return (
        log_dir / RUN_LOG_NAME,
        log_dir / RUN_LATEST_NAME,
        log_dir / RUN_LOCK_NAME,
    )


@contextmanager
def _exclusive_run_lock(lock_path: Path) -> Iterator[bool]:
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+", encoding="utf-8") as handle:
        acquired = False
        try:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
            except BlockingIOError:
                yield False
                return
            yield True
        finally:
            if acquired:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _scan_summary(result: dict[str, Any]) -> dict[str, Any]:
    def _ids(items: Any) -> list[str]:
        if not isinstance(items, list):
            return []
        return sorted(
            {
                str(item["workflow_run_id"])
                for item in items
                if isinstance(item, dict) and item.get("workflow_run_id")
            }
        )

    errors = result.get("errors", [])
    return {
        "run_count": int(result.get("run_count", 0) or 0),
        "waiting_count": int(result.get("waiting_count", 0) or 0),
        "due_count": int(result.get("due_count", 0) or 0),
        "expired_count": int(result.get("expired_count", 0) or 0),
        "error_count": len(errors) if isinstance(errors, list) else 0,
        "due_workflow_run_ids": _ids(result.get("due")),
        "expired_workflow_run_ids": _ids(result.get("expired")),
    }


def _persist_run(omo_dir: Path, summary: dict[str, Any]) -> None:
    log_path, latest_path, _ = _paths(omo_dir)
    AppendOnlyLog(log_path, lock=fcntl_lock(log_path.with_suffix(".lock"))).append(
        summary, sort_keys=True
    )
    write_text_atomic(
        latest_path,
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True),
    )


def read_latest_approval_timeout_run(omo_dir: Path) -> dict[str, Any] | None:
    log_path, latest_path, _ = _paths(omo_dir)
    if latest_path.is_file():
        try:
            value = json.loads(latest_path.read_text(encoding="utf-8"))
            if isinstance(value, dict) and value.get("schema") == RUN_SCHEMA:
                return value
        except (OSError, json.JSONDecodeError):
            pass
    entries = AppendOnlyLog(log_path).tail(1)
    return entries[-1] if entries and entries[-1].get("schema") == RUN_SCHEMA else None


def run_once(
    omo_dir: Path | str,
    *,
    now: str | None = None,
    apply: bool = False,
    reason: str = "approval_timeout",
) -> dict[str, Any]:
    """Run one governed scan and persist a privacy-safe execution summary."""
    root = Path(omo_dir)
    observed_at = _stamp(now)
    started_at = _stamp()
    _, _, lock_path = _paths(root)
    summary: dict[str, Any] = {
        "schema": RUN_SCHEMA,
        "run_id": f"approval-timeout-run:{uuid4().hex}",
        "started_at": started_at,
        "finished_at": _stamp(),
        "observed_at": observed_at,
        "mode": "apply" if apply else "dry_run",
        "apply": apply,
        "reason": reason,
        "status": "failed",
        "scan": {
            "run_count": 0,
            "waiting_count": 0,
            "due_count": 0,
            "expired_count": 0,
            "error_count": 0,
            "due_workflow_run_ids": [],
            "expired_workflow_run_ids": [],
        },
        "errors": [],
    }

    with _exclusive_run_lock(lock_path) as acquired:
        if not acquired:
            summary["status"] = "skipped"
            summary["skip_reason"] = "already_running"
        else:
            try:
                result = scan_approval_timeouts(
                    root, now=observed_at, apply=apply, reason=reason
                )
                summary["scan"] = _scan_summary(result)
                summary["errors"] = result.get("errors", [])
                summary["status"] = "completed" if not summary["errors"] else "degraded"
            except (OSError, ValueError, ApprovalLifecycleError) as exc:
                summary["errors"] = [{"code": "scan_failed", "error": str(exc)}]
                summary["status"] = "failed"

    summary["finished_at"] = _stamp()
    try:
        _persist_run(root, summary)
        summary["ledger_recorded"] = True
    except (OSError, TypeError, ValueError) as exc:
        summary["ledger_recorded"] = False
        summary["status"] = "failed"
        summary.setdefault("errors", []).append(
            {"code": "ledger_write_failed", "error": str(exc)}
        )
    return summary


__all__ = [
    "RUN_LATEST_NAME",
    "RUN_LOCK_NAME",
    "RUN_LOG_NAME",
    "RUN_SCHEMA",
    "read_latest_approval_timeout_run",
    "run_once",
]
