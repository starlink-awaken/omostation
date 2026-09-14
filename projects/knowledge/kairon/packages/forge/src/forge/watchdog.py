#!/usr/bin/env python3
"""
forge-watchdog — 健康检查看门狗守护进程

定时运行健康检查，在状态发生切换时发送通知。

用法:
  python3 src/watchdog.py [选项]

选项:
  --interval SECONDS    检查间隔（秒，默认 300）
  --notify TYPE         通知类型: ntfy（默认）, discord, both
  --daemon              后台运行（double-fork）
  --help                显示此帮助
"""

import json
import logging
import os
import signal
import subprocess
import sys
import time
from typing import Any

from forge.forge_config import LOG_DIR, SRC  # type: ignore[import-not-found]

LOG_FILE = LOG_DIR / "forge-watchdog.log"
PID_FILE = LOG_DIR / "forge-watchdog.pid"
HEALTH_CHECK = SRC / "health_check.py"

# 状态跟踪：None = 首次/未知, True = 健康, False = 不健康
_last_healthy = None


def _setup_logging(*, console: bool = True) -> None:
    """配置日志：文件日志 + 可选控制台输出"""
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger()
    for h in root.handlers[:]:
        root.removeHandler(h)
        h.close()

    handlers: list[logging.Handler] = [logging.FileHandler(str(LOG_FILE))]
    if console:
        handlers.append(logging.StreamHandler())

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=handlers,
    )


def _send_notification(message: str, notify_type: str) -> None:
    """通过配置的渠道发送通知。缺失环境变量时静默降级。"""
    if notify_type in ("ntfy", "both"):
        topic = os.environ.get("NTFY_TOPIC")
        if topic:
            try:
                subprocess.run(
                    ["curl", "-s", "-X", "POST", "-d", message, f"https://ntfy.sh/{topic}"],
                    capture_output=True,
                    timeout=10,
                )
            except Exception as e:
                logging.warning("ntfy 通知失败: %s", e)
        else:
            logging.warning("NTFY_TOPIC 未设置，跳过 ntfy 通知")

    if notify_type in ("discord", "both"):
        webhook = os.environ.get("DISCORD_WEBHOOK")
        if webhook:
            try:
                payload = json.dumps({"content": message})
                subprocess.run(
                    ["curl", "-s", "-X", "POST", "-H", "Content-Type: application/json", "-d", payload, webhook],
                    capture_output=True,
                    timeout=10,
                )
            except Exception as e:
                logging.warning("Discord 通知失败: %s", e)
        else:
            logging.warning("DISCORD_WEBHOOK 未设置，跳过 Discord 通知")


def _run_health_check() -> tuple[bool, str]:
    """执行 health_check.py，返回 (是否健康, 输出文本)。"""
    try:
        r = subprocess.run(
            [sys.executable, str(HEALTH_CHECK)],
            capture_output=True,
            text=True,
            timeout=60,
        )
        return r.returncode == 0, (r.stdout + r.stderr).strip()
    except FileNotFoundError:
        return False, f"health_check.py 不存在: {HEALTH_CHECK}"
    except subprocess.TimeoutExpired:
        return False, "health_check.py 执行超时（60 秒）"
    except Exception as e:
        return False, f"health_check.py 错误: {e}"


def _daemonize() -> None:
    """Double-fork 达到守护进程化（脱离控制终端）。"""
    try:
        pid = os.fork()
        if pid > 0:
            sys.exit(0)
    except OSError as e:
        logging.error("第一次 fork 失败: %s", e)
        sys.exit(1)

    try:
        os.setsid()
    except OSError as e:
        logging.error("setsid 失败: %s", e)
        sys.exit(1)

    os.umask(0)
    os.chdir("/")

    try:
        pid = os.fork()
        if pid > 0:
            sys.exit(0)
    except OSError as e:
        logging.error("第二次 fork 失败: %s", e)
        sys.exit(1)

    sys.stdout.flush()
    sys.stderr.flush()

    with open(os.devnull) as si, open(os.devnull, "a+") as so, open(os.devnull, "a+") as se:
        os.dup2(si.fileno(), sys.stdin.fileno())
        os.dup2(so.fileno(), sys.stdout.fileno())
        os.dup2(se.fileno(), sys.stderr.fileno())


def _write_pid() -> None:
    PID_FILE.write_text(str(os.getpid()))


def _remove_pid() -> None:
    try:
        if PID_FILE.exists():
            PID_FILE.unlink()
    except Exception:
        pass


def _signal_handler(signum: int, frame: Any) -> None:
    logging.info("收到信号 %d，正在关闭", signum)
    _remove_pid()
    sys.exit(0)


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Forge 健康检查看门狗守护进程",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=300,
        help="检查间隔（秒，默认 300）",
    )
    parser.add_argument(
        "--notify",
        choices=["ntfy", "discord", "both"],
        default="ntfy",
        help="通知类型（默认: ntfy）",
    )
    parser.add_argument(
        "--daemon",
        action="store_true",
        help="后台运行（double-fork）",
    )

    args = parser.parse_args()
    interval = max(1, args.interval)
    notify_type = args.notify

    # 守护进程化之前配置日志（含控制台）
    _setup_logging(console=True)
    logging.info(
        "Forge Watchdog 启动（interval=%ds, notify=%s, daemon=%s）",
        interval,
        notify_type,
        args.daemon,
    )

    if args.daemon:
        logging.info("守护进程化...")
        _daemonize()
        # 守护进程后重新配置日志（仅文件，stdout/stderr 已重定向到 /dev/null）
        _setup_logging(console=False)
        logging.info("守护进程已启动（PID: %d）", os.getpid())

    _write_pid()
    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    global _last_healthy

    try:
        while True:
            healthy, output = _run_health_check()

            if _last_healthy is None:
                logging.info(
                    "首次健康检查: %s",
                    "HEALTHY" if healthy else "UNHEALTHY",
                )
                if not healthy:
                    logging.warning("输出: %s", output[:200])
            elif healthy and not _last_healthy:
                # 不健康 → 健康：发送恢复通知
                msg = "Forge: Service recovered"
                logging.info("状态切换: UNHEALTHY -> HEALTHY. %s", msg)
                _send_notification(msg, notify_type)
            elif not healthy and _last_healthy:
                # 健康 → 不健康：发送告警通知
                msg = f"Forge: Service unhealthy\n{output[:500]}"
                logging.warning("状态切换: HEALTHY -> UNHEALTHY. %s", msg)
                _send_notification(msg, notify_type)
            else:
                logging.debug(
                    "健康检查: %s（无变化）",
                    "HEALTHY" if healthy else "UNHEALTHY",
                )

            _last_healthy = healthy
            time.sleep(interval)

    except KeyboardInterrupt:
        logging.info("收到 SIGINT，正在关闭")
        _remove_pid()
    except Exception as e:
        logging.error("意外错误: %s", e)
        _remove_pid()
        return 1

    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
