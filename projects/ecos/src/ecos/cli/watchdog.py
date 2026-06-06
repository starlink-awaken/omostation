#!/usr/bin/env python3
"""
ecos_watchdog.py — eCOS Phase 3 告警自愈系统

监控 BOS / KOS / Forge / Agora / agentmesh 端口健康
故障检测：连续 N 次健康检查失败判定为宕机
自动恢复：自启动各 daemon
通知：stdout 输出 = 异常状态（供 cron no_agent 采集推微信）

用法:
  python3 scripts/ecos_watchdog.py              # 单次检测
  python3 scripts/ecos_watchdog.py --check      # 同默认
  python3 scripts/ecos_watchdog.py --once       # 单次检测 + stdout 输出（给 cron 用）
"""

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path


# ── Forge Registry bootstrap ──────────────────────────────────────────────
def _load_forge_env() -> None:
    """Load environment variables from Forge Registry via config.py env."""
    config_py = os.path.expanduser("~/.workspace/config.py")
    if not os.path.isfile(config_py):
        return
    try:
        result = subprocess.run(
            ["python3", config_py, "env"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            for line in result.stdout.strip().splitlines():
                line = line.strip()
                if line.startswith("export "):
                    parts = line[7:].split("=", 1)
                    if len(parts) == 2:
                        key, val = parts[0], parts[1]
                        if key not in os.environ:
                            os.environ[key] = val
    except Exception:
        pass


_load_forge_env()

# ── 监控目标 ──────────────────────────────────────────────
# 仅监控由 launchd 管理的持久 daemon
# kos/agora/forge 是 Hermes MCP stdio 服务，由其自身生命周期管理
HEALTH_CHECKS = {
    "bos-daemon": {
        "restart_cmd": "launchctl start com.sharedbrain.bos",
        "port": int(os.environ.get("BOS_API_PORT", "7420")),
        "detect": "port",
    },
    "agentmesh": {
        "restart_cmd": "launchctl start com.agentmesh.gateway",
        "port": int(os.environ.get("AGENTMESH_PORT", "3000")),
        "detect": "url",
        "url": f"http://127.0.0.1:{os.environ.get('AGENTMESH_PORT', '3000')}/v1/health",
    },
}

# ── 状态持久化 ──────────────────────────────────────────
STATE_DIR = Path(os.path.expanduser("~/.hermes/ecos-watchdog"))
STATE_DIR.mkdir(parents=True, exist_ok=True)
STATE_FILE = STATE_DIR / "failures.json"

# 启动时清除旧状态（防止以前测试跑的遗留计数影响首次生产运行）
_FIRST_RUN_FLAG = STATE_DIR / ".initialized"
if not _FIRST_RUN_FLAG.exists():
    _FIRST_RUN_FLAG.touch()
    STATE_FILE.write_text("{}")
MAX_FAILURES = 3  # 连续失败 N 次视为宕机


def load_state():
    try:
        return json.loads(STATE_FILE.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_state(state):
    STATE_FILE.write_text(json.dumps(state, indent=2))


def check_url(url):
    """HTTP GET 健康检查"""
    try:
        req = urllib.request.Request(url, method="GET")  # noqa: S310
        with urllib.request.urlopen(req, timeout=5) as resp:  # noqa: S310
            body = resp.read().decode()
            return resp.status == 200, body[:200]
    except Exception as e:
        return False, str(e)


def check_port(port):
    """TCP 端口可达性检查"""
    import socket

    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(3)
        s.connect(("127.0.0.1", port))
        s.close()
        return True, ""
    except Exception as e:
        return False, str(e)


def check_proc(proc_match):
    """进程名匹配检查"""
    try:
        result = subprocess.run(
            ["pgrep", "-f", proc_match],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.returncode == 0, result.stdout.strip()
    except Exception as e:
        return False, str(e)


def restart_daemon(name, cmd):
    """启动后台守护进程"""
    expanded = os.path.expanduser(cmd)
    try:
        subprocess.Popen(  # noqa: S602
            expanded,
            shell=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            preexec_fn=os.setsid,
        )
        print(f"🔧 WATCHDOG: {name} 重启信号已发送")
        return True
    except Exception as e:
        print(f"❌ WATCHDOG: {name} 重启失败: {e}")
        return False


def run_once(verbose=True):
    """执行一轮健康检查"""
    state = load_state()
    now = datetime.now(UTC).isoformat()
    failures = []
    restarts = []

    for name, cfg in HEALTH_CHECKS.items():
        alive = False
        detail = ""

        # ── 健康检测策略 ──
        strategy = cfg.get("detect", "proc")
        if strategy == "url":
            alive, detail = check_url(cfg["url"])
        elif strategy == "port":
            alive, detail = check_port(cfg["port"])
            if not alive and cfg.get("proc_match"):
                alive, detail = check_proc(cfg["proc_match"])
        else:  # proc
            alive, detail = check_proc(cfg.get("proc_match", name))

        # ── 故障计数器 ──
        prev = state.get(name, {"failures": 0})
        if alive:
            state[name] = {"failures": 0, "last_ok": now}
            if verbose:
                print(f"✅ {name} 健康")
        else:
            f_count = prev.get("failures", 0) + 1
            state[name] = {"failures": f_count, "last_fail": now, "detail": detail}

            if f_count >= MAX_FAILURES:
                print(f"🚨 WATCHDOG: {name} 宕机 (连续{f_count}次失败) — {detail}")
                failures.append(name)
                # 自动重启
                if cfg.get("restart_cmd"):
                    restart_daemon(name, cfg["restart_cmd"])
                    restarts.append(name)
                    state[name] = {"failures": 0, "restarted_at": now}
            else:
                if verbose:
                    print(f"⚠️  {name} 异常 (第{f_count}/{MAX_FAILURES}次) — {detail}")

    save_state(state)

    # ── 输出告警摘要（供 cron no_agent 采集）──
    if failures:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        lines = [f"🚨 [eCOS Watchdog] {timestamp}"]
        for f in failures:
            lines.append(f"  - {f}: 已触发重启")
        for r in restarts:
            lines.append(f"  - {r}: 重启命令已发送")
        lines.append("")
        lines.append("--- 当前健康状态 ---")
        for name in HEALTH_CHECKS:
            s = state.get(name, {})
            if s.get("failures", 0) == 0:
                lines.append(f"  ✅ {name}")
            else:
                lines.append(f"  ⚠️  {name} ({s.get('failures', 0)}次失败)")
        print("\n".join(lines))
        return False
    return True


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "check"

    if mode == "--once":
        # 单次检测，输出供 cron 采集
        ok = run_once(verbose=False)
        if ok:
            # 健康时静默（no_agent 模式下空输出 = 不通知）
            pass
        sys.exit(0 if ok else 1)

    elif mode == "--daemon":
        # 持续循环模式
        interval = int(sys.argv[2]) if len(sys.argv) > 2 else 60
        print(f"🔍 eCOS Watchdog daemon 启动 — 每 {interval}s 检测一次")
        while True:
            run_once(verbose=True)
            time.sleep(interval)

    else:
        # 默认单次 verbose
        run_once(verbose=True)


if __name__ == "__main__":
    main()
