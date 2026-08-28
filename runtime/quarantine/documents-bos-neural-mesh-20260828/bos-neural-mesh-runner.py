#!/usr/bin/env python3
"""BOS Neural Mesh governed runner.

This entry point orchestrates connectors without treating a partial run as a
success. Raw connector output is never echoed to the terminal; only run and
step metadata are written to the local state database.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import sqlite3
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_DOCS_ROOT = Path(os.environ.get("BOS_DOCS_ROOT", "/Users/xiamingxing/Documents"))
DEFAULT_RUNTIME_DIR = DEFAULT_DOCS_ROOT / "@公共" / "_runtime"
DEFAULT_STATE_DB = DEFAULT_RUNTIME_DIR / "bos-neural-mesh-state.sqlite"
DEFAULT_TIMEOUT = int(os.environ.get("BOS_NEURAL_MESH_STEP_TIMEOUT", "1800"))


@dataclass(frozen=True)
class Step:
    step_id: str
    label: str
    script_name: str
    domain: str
    sensitive: bool = False
    derived: bool = False


STEPS = (
    Step("private-ingest", "本地私有源采集", "universal-private-ingest.py", "personal", True),
    Step("apple-mail", "Apple Mail 解析", "apple-mail-ingest.py", "personal", True),
    Step("netease-mail", "网易邮箱大师解析", "netease-mailmaster-ingest.py", "personal", True),
    Step("seeyon-oa", "致远 OA 解析", "seeyon-auto-login-fetch.py", "official_work", True),
    Step("kems-materialize", "KEMS 图谱持久化", "kems-materialize.py", "derived", True, True),
    Step("embedding", "向量抽取与归仓", "omlxc-embedding-bridge.py", "derived", False, True),
    Step("mesh-dispatch", "知识网分流", "mesh-dynamic-dispatcher.py", "derived", False, True),
    Step("reachbridge", "外部触达分发", "reachbridge-enterprise-gateway.py", "derived", False, True),
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_state(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS runs (
                run_id TEXT PRIMARY KEY,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                status TEXT NOT NULL,
                docs_root TEXT NOT NULL,
                dry_run INTEGER NOT NULL,
                allow_derived INTEGER NOT NULL,
                error_count INTEGER NOT NULL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS steps (
                run_id TEXT NOT NULL,
                step_id TEXT NOT NULL,
                label TEXT NOT NULL,
                script_path TEXT NOT NULL,
                domain TEXT NOT NULL,
                status TEXT NOT NULL,
                started_at TEXT,
                finished_at TEXT,
                return_code INTEGER,
                error_type TEXT,
                PRIMARY KEY (run_id, step_id),
                FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE
            );
                """
        )
    db_path.chmod(0o600)


def create_run(db_path: Path, run_id: str, docs_root: Path, dry_run: bool, allow_derived: bool) -> None:
    with sqlite3.connect(db_path) as db:
        db.execute(
            "INSERT INTO runs VALUES (?, ?, NULL, ?, ?, ?, ?, 0)",
            (run_id, utc_now(), "running", str(docs_root), int(dry_run), int(allow_derived)),
        )


def save_step(db_path: Path, run_id: str, step: Step, script: Path, status: str, **extra: object) -> None:
    with sqlite3.connect(db_path) as db:
        db.execute(
            """INSERT INTO steps VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(run_id, step_id) DO UPDATE SET status=excluded.status,
              finished_at=excluded.finished_at, return_code=excluded.return_code,
              error_type=excluded.error_type""",
            (
                run_id,
                step.step_id,
                step.label,
                str(script),
                step.domain,
                status,
                extra.get("started_at"),
                extra.get("finished_at"),
                extra.get("return_code"),
                extra.get("error_type"),
            ),
        )


def finish_run(db_path: Path, run_id: str, status: str, error_count: int) -> None:
    with sqlite3.connect(db_path) as db:
        db.execute(
            "UPDATE runs SET finished_at=?, status=?, error_count=? WHERE run_id=?",
            (utc_now(), status, error_count, run_id),
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the governed BOS Neural Mesh pipeline")
    parser.add_argument("--dry-run", action="store_true", help="validate the plan without invoking connectors")
    parser.add_argument("--allow-derived", action="store_true", help="explicitly allow vector/graph/dispatch steps")
    parser.add_argument(
        "--production", action="store_true", help="run the fail-closed production preflight before connectors"
    )
    parser.add_argument("--docs-root", type=Path, default=DEFAULT_DOCS_ROOT)
    parser.add_argument("--state-db", type=Path, default=DEFAULT_STATE_DB)
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    return parser.parse_args()


def _runtime_root() -> Path | None:
    configured = Path(os.environ.get("BOS_RUNTIME_ROOT", "")).expanduser()
    workspace = Path(os.environ.get("BOS_WORKSPACE_ROOT", "/Users/xiamingxing/Workspace"))
    candidates = (
        configured,
        workspace / "projects" / "runtime",
        Path("/Users/xiamingxing/ws-runtime-kems-m6-20260731"),
    )
    return next(
        (
            candidate
            for candidate in candidates
            if candidate and (candidate / "scripts" / "kems_production_preflight.py").is_file()
        ),
        None,
    )


def run_production_preflight(
    args: argparse.Namespace, docs_root: Path, state_db: Path, run_id: str, runtime_dir: Path
) -> bool:
    step = Step("production-preflight", "生产上线前置闸门", "kems_production_preflight.py", "governance", False, True)
    runtime_root = _runtime_root()
    script = runtime_root / "scripts" / step.script_name if runtime_root else runtime_dir / step.script_name
    if not script.is_file():
        save_step(state_db, run_id, step, script, "failed", finished_at=utc_now(), error_type="missing_preflight")
        return False
    save_step(state_db, run_id, step, script, "running", started_at=utc_now())
    workspace_root = Path(os.environ.get("BOS_WORKSPACE_ROOT", "/Users/xiamingxing/Workspace"))
    evidence_output = runtime_dir / "evidence" / f"production-preflight-{run_id}.json"
    command = [
        sys.executable,
        str(script),
        "--docs-root",
        str(docs_root),
        "--omo-root",
        str(workspace_root / ".omo"),
        "--evidence-output",
        str(evidence_output),
        "--production",
    ]
    try:
        result = subprocess.run(
            command,
            cwd=runtime_root or runtime_dir,
            env={**os.environ, "BOS_DOCS_ROOT": str(docs_root), "BOS_MESH_RUN_ID": run_id},
            capture_output=True,
            text=True,
            timeout=min(args.timeout, 60),
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        save_step(state_db, run_id, step, script, "failed", finished_at=utc_now(), error_type="preflight_error")
        return False
    if result.returncode:
        save_step(
            state_db,
            run_id,
            step,
            script,
            "blocked",
            finished_at=utc_now(),
            return_code=result.returncode,
            error_type="preflight_blocked",
        )
        return False
    save_step(state_db, run_id, step, script, "succeeded", finished_at=utc_now(), return_code=0)
    return True


def run_pipeline(args: argparse.Namespace) -> int:
    docs_root = args.docs_root.expanduser().resolve()
    runtime_dir = docs_root / "@公共" / "_runtime"
    state_db = args.state_db.expanduser().resolve()
    init_state(state_db)
    run_id = f"bos-mesh-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{os.getpid()}"
    create_run(state_db, run_id, docs_root, args.dry_run, args.allow_derived)
    errors = 0

    try:
        if (
            args.production
            and not args.dry_run
            and not run_production_preflight(args, docs_root, state_db, run_id, runtime_dir)
        ):
            errors += 1
        for step in STEPS:
            if errors:
                break
            script = runtime_dir / step.script_name
            if args.dry_run:
                status = "planned" if script.is_file() else "failed"
                save_step(
                    state_db,
                    run_id,
                    step,
                    script,
                    status,
                    finished_at=utc_now(),
                    error_type=None if script.is_file() else "missing_script",
                )
                if status == "failed":
                    errors += 1
                    break
                continue
            if step.derived and not args.allow_derived:
                save_step(
                    state_db, run_id, step, script, "blocked", finished_at=utc_now(), error_type="derived_not_allowed"
                )
                errors += 1
                break
            if not script.is_file():
                save_step(state_db, run_id, step, script, "failed", finished_at=utc_now(), error_type="missing_script")
                errors += 1
                break
            started_at = utc_now()
            save_step(state_db, run_id, step, script, "running", started_at=started_at)
            try:
                command = [sys.executable, str(script)]
                if step.step_id == "reachbridge" and args.production:
                    command.append("--production")
                result = subprocess.run(
                    command,
                    cwd=runtime_dir,
                    env={
                        **os.environ,
                        "BOS_DOCS_ROOT": str(docs_root),
                        "BOS_WORKSPACE_ROOT": os.environ.get("BOS_WORKSPACE_ROOT", "/Users/xiamingxing/Workspace"),
                        "BOS_MESH_RUN_ID": run_id,
                        "BOS_MESH_STATE_DB": str(state_db),
                        "BOS_MESH_STEP_ID": step.step_id,
                    },
                    capture_output=True,
                    text=True,
                    timeout=args.timeout,
                    check=False,
                )
                if result.returncode:
                    errors += 1
                    save_step(
                        state_db,
                        run_id,
                        step,
                        script,
                        "failed",
                        finished_at=utc_now(),
                        return_code=result.returncode,
                        error_type="nonzero_exit",
                    )
                    break
                save_step(state_db, run_id, step, script, "succeeded", finished_at=utc_now(), return_code=0)
            except subprocess.TimeoutExpired:
                errors += 1
                save_step(state_db, run_id, step, script, "failed", finished_at=utc_now(), error_type="timeout")
                break
            except OSError as exc:
                errors += 1
                save_step(
                    state_db, run_id, step, script, "failed", finished_at=utc_now(), error_type=type(exc).__name__
                )
                break
    finally:
        status = "succeeded" if errors == 0 else "failed"
        finish_run(state_db, run_id, status, errors)

    print(
        json.dumps(
            {"run_id": run_id, "status": status, "error_count": errors, "state_db": str(state_db)}, ensure_ascii=False
        )
    )
    return 0 if status == "succeeded" else 1


def main() -> int:
    args = parse_args()
    lock_path = args.state_db.expanduser().with_suffix(args.state_db.suffix + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("w", encoding="utf-8") as lock:
        lock_path.chmod(0o600)
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print(json.dumps({"status": "blocked", "error": "another run is active"}, ensure_ascii=False))
            return 2
        return run_pipeline(args)


if __name__ == "__main__":
    raise SystemExit(main())
