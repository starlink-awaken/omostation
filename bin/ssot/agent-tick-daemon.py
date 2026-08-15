#!/usr/bin/env python3
"""Agent Tick Daemon — AgentHost 持续运行 (AGENT-01).

让 AgentHost 的 agent 自主 tick (非被手动/一次性触发), 具备持续运行能力.
复用 projects/omo 的 run_agent_tick, 循环调度 + 心跳日志.

Usage:
  python3 bin/ssot/agent-tick-daemon.py --once        # 单次 tick
  python3 bin/ssot/agent-tick-daemon.py --run          # 持续运行 (默认)
  python3 bin/ssot/agent-tick-daemon.py --interval 60  # tick 间隔
  python3 bin/ssot/agent-tick-daemon.py --max-ticks 10 # 运行 N 次后停止
  python3 bin/ssot/agent-tick-daemon.py --workspace-root ~/Workspace
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from _shared import ROOT, append_jsonl, utc_now

CODE_ROOT = ROOT
OMO_SRC = CODE_ROOT / "projects" / "omo" / "src"


def _configure_runtime_workspace(configured: str | Path | None) -> Path:
    """Bind runtime reads/writes to one explicit workspace, separate from code root."""
    configured_value = (
        configured
        if configured is not None
        else os.environ.get("WORKSPACE_ROOT", str(CODE_ROOT))
    )
    expanded = os.path.expanduser(os.fspath(configured_value))
    if not os.path.isabs(expanded) or any(
        component in {".", ".."} for component in expanded.split(os.sep)
    ):
        raise ValueError(f"runtime workspace path must be canonical: {expanded}")
    absolute_raw = Path(expanded)
    if any(part.is_symlink() for part in (absolute_raw, *absolute_raw.parents)):
        raise ValueError(f"runtime workspace symlink is not allowed: {absolute_raw}")
    try:
        workspace = absolute_raw.resolve(strict=True)
    except (FileNotFoundError, OSError) as exc:
        raise ValueError(f"runtime workspace is unavailable: {absolute_raw}") from exc
    if not workspace.is_dir() or not (workspace / ".omo").is_dir():
        raise ValueError(
            f"runtime workspace must contain a .omo directory: {workspace}"
        )
    os.environ["WORKSPACE_CODE_ROOT"] = str(CODE_ROOT)
    os.environ["WORKSPACE_ROOT"] = str(workspace)
    return workspace


def _runtime_workspace() -> Path:
    return _configure_runtime_workspace(os.environ.get("WORKSPACE_ROOT"))


def _load_omo() -> Any:
    """Load omo.run_agent_tick (sys.path 注入, 复用现有 AgentHost)."""
    if str(OMO_SRC) not in sys.path:
        sys.path.insert(0, str(OMO_SRC))
    from omo.omo_agent_host import run_agent_tick

    return run_agent_tick


def _heartbeat(entry: dict[str, Any]) -> None:
    entry.setdefault("ts", utc_now())
    append_jsonl(
        _runtime_workspace() / ".omo" / "state" / "agent-tick-daemon.jsonl",
        entry,
    )


def _coordination_heartbeat(result: dict[str, Any]) -> None:
    """BET-Y1Q1-T1-05A: 巡检结果顺写共享协调层 agent_health 表.

    shadow 语义: 协调层写入失败不反噬 tick 主流程 (F14 错误隔离同款),
    只 stderr 警告 — agent_health 是镜像, 不是权威.
    """
    try:
        sys.path.insert(0, str(CODE_ROOT / "bin" / "gac"))
        import coordination_store

        runtime_attestation = _runtime_attestation()
        for r in result.get("results", []) or []:
            agent_id = r.get("agent_id")
            if not agent_id:
                continue
            ok = bool(r.get("ok"))
            coordination_store.heartbeat(
                agent_id,
                "ok" if ok else "fail",
                source="tick",
                detail={
                    "action": r.get("action"),
                    "error": r.get("error"),
                    "runtime_attestation": runtime_attestation,
                },
            )
    except Exception as exc:  # noqa: BLE001 — shadow 镜像不反噬主流程
        print(f"[tick-coordination] heartbeat mirror failed: {exc}", file=sys.stderr)


def _runtime_attestation() -> dict[str, str]:
    """不含路径/用户名/主机名的运行代码指纹，供识别 launchd 部署漂移."""
    code_sha256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    runtime_root_digest = hashlib.sha256(str(_runtime_workspace()).encode()).hexdigest()
    revision = "unavailable"
    try:
        result = subprocess.run(
            ["git", "-C", str(CODE_ROOT), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            revision = result.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        pass
    return {
        "component": "agent-tick-daemon",
        "code_sha256": code_sha256,
        "workspace_revision": revision,
        "python_version": platform.python_version(),
        "runtime_root_digest": runtime_root_digest,
    }


def run_once() -> dict[str, Any]:
    """Run one tick_all pass over all registered agents."""
    run_agent_tick = _load_omo()
    result = run_agent_tick()
    heartbeat = {
        "type": "agent_tick",
        "agent_count": result.get("agent_count", 0),
        "ok_count": result.get("ok_count", 0),
        "failed_count": result.get("failed_count", 0),
        "actions": [r.get("action") for r in result.get("results", [])],
    }
    _heartbeat(heartbeat)
    _coordination_heartbeat(result)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true", help="run single tick and exit")
    parser.add_argument("--run", action="store_true", help="run continuously (default)")
    parser.add_argument("--interval", type=int, default=60, help="tick interval seconds")
    parser.add_argument("--max-ticks", type=int, default=None, help="stop after N ticks")
    parser.add_argument(
        "--workspace-root",
        help="authoritative runtime workspace root; code continues loading from this checkout",
    )
    args = parser.parse_args(argv)
    try:
        _configure_runtime_workspace(args.workspace_root)
    except ValueError as exc:
        parser.error(str(exc))

    if args.once:
        result = run_once()
        print(json.dumps({
            "mode": "once",
            "agent_count": result.get("agent_count"),
            "ok_count": result.get("ok_count"),
            "failed_count": result.get("failed_count"),
            "results": result.get("results"),
        }, ensure_ascii=False, indent=2, sort_keys=True))
        return 0

    print(f"Agent Tick Daemon running (interval={args.interval}s, "
          f"max_ticks={args.max_ticks or '∞'}). Ctrl+C to stop.", flush=True)
    ticks = 0
    try:
        while True:
            ticks += 1
            result = run_once()
            print(f"  [{ticks}] tick: {result.get('ok_count')}/{result.get('agent_count')} ok",
                  flush=True)
            if args.max_ticks and ticks >= args.max_ticks:
                print(f"Reached max_ticks={args.max_ticks}. Stopping.")
                break
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print(f"\nDaemon stopped after {ticks} ticks.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
