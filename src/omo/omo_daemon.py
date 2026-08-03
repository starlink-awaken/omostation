"""OMO sync daemon — 30min tick 守护进程(从 kairon_governance.daemon 迁移).

设计:
  - 30 分钟 tick (可配)
  - PID file: /tmp/omo-governance-daemon.pid (优先); 兼容旧 /tmp/kairon-governance-daemon.pid
  - 日志: .omo/_delivery/daemon.log (append)
  - 每个 tick: audit (skip agora_health) -> history append -> sync (dry-run) -> Mesh watchdog (dry-run)
  - 优雅 stop: SIGTERM / SIGINT
  - 启动失败: 立即报错
  - **只读**: daemon 不写 system.yaml (sync 走 dry-run), 不动 goals / INDEX.md

迁移自: kairon_governance.daemon (P30-W1 GOV-MERGE 落地)
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import signal
import sys
import threading
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from omo.mesh_watchdog_runner import run_once as run_mesh_watchdog_once
from omo.omo_audit import run_governance_audit
from omo.omo_history import DEFAULT_PATH as DEFAULT_HISTORY_PATH
from omo.omo_history import append_entry
from omo.omo_paths import DAEMON_LOG_FILE, DAEMON_PID_FILE, OMO_ROOT

# ── 默认配置 ────────────────────────────────────────────
DEFAULT_INTERVAL_SECONDS = 1800  # 30 min

# 旧 kairon-governance PID 路径 — 保持兼容, 防止升级期双 daemon
LEGACY_PID_FILE = Path("/tmp/kairon-governance-daemon.pid")

# 同步 state.yaml 的函数 (延迟 import, 避免循环)
_sync_module = None


def _ensure_sync_module():
    """延迟加载 sync_state 函数 (本地副本, 不依赖 kairon_governance)."""
    global _sync_module
    if _sync_module is not None:
        return _sync_module

    from omo.omo_audit_sync import (  # type: ignore[import-not-found]
        collect_actual_state,
        diff_with_system_yaml,
        read_system_yaml,
    )
    from omo.omo_paths import OMO_ROOT

    _sync_module = {
        "collect": collect_actual_state,
        "diff": diff_with_system_yaml,
        "read": read_system_yaml,
        "system_yaml": OMO_ROOT / "state" / "system.yaml",
    }
    return _sync_module


# ── 数据结构 ────────────────────────────────────────────


@dataclass
class TickResult:
    """单次 tick 的执行结果."""

    timestamp: str
    audit_score: float | None
    audit_grade: str | None
    sync_diff_count: int
    history_appended: bool
    error: str | None = None
    mesh_watchdog: dict[str, Any] | None = None

    def to_dict(self) -> dict:
        return asdict(self)


# ── PID file 管理 (兼容新旧) ──────────────────────────────


def _read_pid_file(pid_file: Path) -> int | None:
    try:
        return int(pid_file.read_text().strip())
    except (ValueError, OSError):
        return None


def _is_daemon_running(pid_file: Path = DAEMON_PID_FILE) -> int | None:
    """检查 daemon 是否在跑 (返回 PID 或 None).

    兼容: 同时检查新 omo PID 与旧 kairon-governance PID 文件.
    """
    for candidate in (pid_file, LEGACY_PID_FILE):
        if not candidate.exists():
            continue
        pid = _read_pid_file(candidate)
        if pid is None:
            continue
        try:
            os.kill(pid, 0)  # 信号 0 只检查不杀
            return pid
        except OSError:
            # PID 文件损坏或进程已死
            try:
                candidate.unlink(missing_ok=True)
            except OSError:
                pass
    return None


def _write_pid_file(pid_file: Path = DAEMON_PID_FILE) -> None:
    pid_file.parent.mkdir(parents=True, exist_ok=True)
    pid_file.write_text(str(os.getpid()))


def _clear_pid_file(pid_file: Path = DAEMON_PID_FILE) -> None:
    pid_file.unlink(missing_ok=True)


# ── 日志 ─────────────────────────────────────────────


def _setup_logging(log_file: Path = DAEMON_LOG_FILE) -> logging.Logger:
    log_file.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("omo.daemon")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        handler = logging.FileHandler(log_file, encoding="utf-8")
        handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
        )
        logger.addHandler(handler)
        sh = logging.StreamHandler(sys.stdout)
        sh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
        logger.addHandler(sh)
    return logger


# ── 单 tick 执行 ──────────────────────────────────────


def run_once(
    *,
    history_path: Path | None = None,
    mesh_watchdog: bool = False,
    mesh_watchdog_apply: bool = False,
    mesh_watchdog_now: str | None = None,
) -> TickResult:
    """执行一次 tick: audit -> history append -> sync (dry-run).

    daemon 跑时**跳过** agora_health 检查 (避免每 30min 发 11 个 HTTP 请求).
    Mesh watchdog 默认只读；只有显式 apply 配置才允许追加过期事件。
    """
    timestamp = datetime.now(UTC).isoformat()
    audit_score: float | None = None
    audit_grade: str | None = None
    sync_diff_count = 0
    error: str | None = None
    history_appended = False
    mesh_watchdog_result: dict[str, Any] | None = None
    target_history = history_path if history_path is not None else DEFAULT_HISTORY_PATH

    # 1. audit (daemon 跳过 agora 探活)
    from omo.omo_health import ENV_SKIP_AGORA

    try:
        old_env = os.environ.get(ENV_SKIP_AGORA)
        os.environ[ENV_SKIP_AGORA] = "1"
        try:
            report = run_governance_audit()
        finally:
            if old_env is None:
                os.environ.pop(ENV_SKIP_AGORA, None)
            else:
                os.environ[ENV_SKIP_AGORA] = old_env
        audit_score = report.total_score
        audit_grade = report.grade
    except Exception as exc:  # defensive fallback
        error = f"audit_failed: {exc}"

    # 2. history append (audit 成功才写)
    if audit_score is not None:
        try:
            append_entry(
                {
                    "total_score": audit_score,
                    "grade": audit_grade,
                    "watchlist_count": len(report.watchlist),  # type: ignore[reportPossiblyUnboundVariable]
                    "source": "omo_daemon",
                },
                path=target_history,
            )
            history_appended = True
        except Exception as exc:  # defensive fallback
            error = (error + "; " if error else "") + f"history_failed: {exc}"

    # 3. sync dry-run (只 diff, 不写)
    try:
        mod = _ensure_sync_module()
        actual = mod["collect"]()
        try:
            text = mod["read"](mod["system_yaml"])
            diffs = mod["diff"](actual, text)
            sync_diff_count = len(diffs)
        except Exception as exc:  # defensive fallback
            error = (error + "; " if error else "") + f"sync_diff_failed: {exc}"
    except Exception as exc:  # defensive fallback
        error = (error + "; " if error else "") + f"sync_failed: {exc}"

    # The existing daemon owns cadence; the runner owns one safe Mesh scan.
    if mesh_watchdog:
        mesh_watchdog_result = run_mesh_watchdog_once(
            OMO_ROOT,
            now=mesh_watchdog_now,
            apply=mesh_watchdog_apply,
        )
        if mesh_watchdog_result["status"] in {"degraded", "failed"}:
            error = (error + "; " if error else "") + (
                "mesh_watchdog_"
                f"{mesh_watchdog_result['status']}: "
                f"{len(mesh_watchdog_result['errors'])} error(s)"
            )

    result = TickResult(
        timestamp=timestamp,
        audit_score=audit_score,
        audit_grade=audit_grade,
        sync_diff_count=sync_diff_count,
        history_appended=history_appended,
        error=error,
        mesh_watchdog=mesh_watchdog_result,
    )
    # Round 1: emit lifecycle event on bus-foundation. Best-effort, never raises.
    _publish_tick_event(result)
    return result


def _publish_tick_event(result: TickResult) -> None:
    """R3 / Round 1: emit omo:audit:completed (or :failed) on bus-foundation.

    Best-effort: failures are logged but never propagate, so a missing
    bus-foundation or transient publish error cannot break a tick.
    Other omostation consumers (cockpit, kairon, aetherforge) can
    subscribe via ``bus_foundation.facade.event.subscribe("omo:*")``
    to observe omo audit lifecycle.
    """
    try:
        from bus_foundation.facade import event as bus_event
    except ImportError:
        return
    try:
        topic = "omo:audit:completed" if result.error is None else "omo:audit:failed"
        bus_event.publish(
            topic=topic,
            payload={
                "timestamp": result.timestamp,
                "audit_score": result.audit_score,
                "audit_grade": result.audit_grade,
                "sync_diff_count": result.sync_diff_count,
                "history_appended": result.history_appended,
                "error": result.error,
            },
            source_uri="bos://capability/omo/governance",
        )
    except Exception as exc:  # defensive
        # Never let bus publish break the daemon.
        import logging as _logging

        _logging.getLogger("omo.daemon").debug("omo_audit_publish_skipped: %s", exc)


# ── 主循环 ─────────────────────────────────────────────


def run_daemon(
    interval_seconds: int = DEFAULT_INTERVAL_SECONDS,
    *,
    pid_file: Path = DAEMON_PID_FILE,
    log_file: Path = DAEMON_LOG_FILE,
    mesh_watchdog: bool = True,
    mesh_watchdog_apply: bool = False,
) -> None:
    """主 daemon 循环 (阻塞). 重复跑 run_once, 直到 SIGTERM / SIGINT."""
    if (pid := _is_daemon_running(pid_file)) is not None:
        print(f"ERROR: omo daemon 已在跑 (PID {pid})", file=sys.stderr)
        sys.exit(1)

    _write_pid_file(pid_file)
    logger = _setup_logging(log_file)
    logger.info(f"omo_daemon_started pid={os.getpid()} interval={interval_seconds}s")

    # R3 闭环: 注册 mesh event handlers
    from omo.omo_mesh_event_handler import register_mesh_event_handlers

    register_mesh_event_handlers()

    stop_event = threading.Event()

    def _handle_signal(signum, _frame) -> None:  # type: ignore[no-untyped-def]
        logger.info(f"omo_daemon_signal_received signum={signum}")
        stop_event.set()

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    try:
        while not stop_event.is_set():
            tick_result = run_once(
                mesh_watchdog=mesh_watchdog,
                mesh_watchdog_apply=mesh_watchdog_apply,
            )
            if tick_result.error:
                logger.error(f"tick_error: {tick_result.error}")
            else:
                logger.info(
                    f"tick_done score={tick_result.audit_score} "
                    f"diffs={tick_result.sync_diff_count} "
                    f"mesh_watchdog={tick_result.mesh_watchdog is not None}"
                )
            stop_event.wait(interval_seconds)
    finally:
        _clear_pid_file(pid_file)
        logger.info("omo_daemon_stopped")


def stop_daemon(pid_file: Path = DAEMON_PID_FILE) -> bool:
    """停止 daemon. 返回 True 表示成功发信号."""
    pid = _is_daemon_running(pid_file)
    if pid is None:
        return False
    try:
        os.kill(pid, signal.SIGTERM)
        return True
    except OSError:
        return False


def daemon_status(pid_file: Path = DAEMON_PID_FILE) -> dict:
    """查询 daemon 状态."""
    pid = _is_daemon_running(pid_file)
    if pid is None:
        return {
            "running": False,
            "pid": None,
            "pid_file": str(pid_file),
            "log_file": str(DAEMON_LOG_FILE),
        }
    return {
        "running": True,
        "pid": pid,
        "pid_file": str(pid_file),
        "log_file": str(DAEMON_LOG_FILE),
    }


# ── CLI 入口 ────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    print("⚠️ OMO Daemon 独立 CLI 已弃用，请使用 cockpit 替代", file=sys.stderr)
    parser = argparse.ArgumentParser(
        prog="omo daemon",
        description="omo sync daemon — 定期跑 audit + sync (默认 30min tick)",
    )
    sub = parser.add_subparsers(dest="cmd", required=True, metavar="<cmd>")

    p_start = sub.add_parser("start", help="启动 daemon (阻塞)")
    p_start.add_argument(
        "--interval",
        type=int,
        default=DEFAULT_INTERVAL_SECONDS,
        help=f"tick 间隔秒数 (默认 {DEFAULT_INTERVAL_SECONDS})",
    )
    p_start.add_argument(
        "--no-mesh-watchdog",
        action="store_true",
        help="禁用每个 daemon tick 的 Mesh watchdog 扫描",
    )
    p_start.add_argument(
        "--mesh-watchdog-apply",
        action="store_true",
        help="显式允许 watchdog 追加 WorkerLeaseExpired（默认只读）",
    )

    p_stop = sub.add_parser("stop", help="发 SIGTERM 停止 daemon")
    p_stop.add_argument(
        "--pid-file", type=Path, default=DAEMON_PID_FILE, help="PID 文件路径"
    )

    p_status = sub.add_parser("status", help="查询 daemon 状态")
    p_status.add_argument(
        "--pid-file", type=Path, default=DAEMON_PID_FILE, help="PID 文件路径"
    )

    p_once = sub.add_parser("once", help="跑一次 tick 就退出 (用于 cron / 测试)")
    p_once.add_argument("--mesh-watchdog", action="store_true")
    p_once.add_argument("--mesh-watchdog-apply", action="store_true")
    p_once.add_argument("--now")

    args = parser.parse_args(argv)

    if args.cmd == "start":
        run_daemon(
            interval_seconds=args.interval,
            mesh_watchdog=not args.no_mesh_watchdog,
            mesh_watchdog_apply=args.mesh_watchdog_apply,
        )
        return 0
    if args.cmd == "stop":
        if stop_daemon(args.pid_file):
            print("omo daemon stop signal sent")
            return 0
        print("omo daemon not running")
        return 1
    if args.cmd == "status":
        print(json.dumps(daemon_status(args.pid_file), indent=2))
        return 0
    if args.cmd == "once":
        result = run_once(
            mesh_watchdog=args.mesh_watchdog,
            mesh_watchdog_apply=args.mesh_watchdog_apply,
            mesh_watchdog_now=args.now,
        )
        print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
        return 0
    parser.print_help()
    return 2


__all__ = (
    "DAEMON_LOG_FILE",
    "DAEMON_PID_FILE",
    "DEFAULT_HISTORY_PATH",
    "DEFAULT_INTERVAL_SECONDS",
    "LEGACY_PID_FILE",
    "TickResult",
    "daemon_status",
    "run_daemon",
    "run_once",
    "stop_daemon",
)


if __name__ == "__main__":
    raise SystemExit(main())
