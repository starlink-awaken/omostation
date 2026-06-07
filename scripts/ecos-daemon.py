#!/usr/bin/env python3
"""
eCOS v5 — 自治运维守护进程 (ecos-daemon.py)
=============================================
Phase 7.6 / ADT-02 修复 — Python 替代 bash daemon。
消除单点故障：try/except 兜底 · 持久 SQLite · 信号处理 · 结构化日志。

用法:
    python3 ecos-daemon.py              # 单次运行 (launchd 调用)
    python3 ecos-daemon.py --watch      # 持续监听模式 (启动后循环)
    python3 ecos-daemon.py --status     # 查看 daemon 状态
"""

import sys
import json
import subprocess
import time
import os
import signal
import sqlite3
import argparse
from datetime import datetime, timezone, timedelta
from pathlib import Path


# ── 路径 ──
HOME = Path.home()
DOCS = HOME / "Documents"
ECOS = HOME / ".ecos"
WORKSPACE = HOME / "Workspace"
SCRIPTS = ECOS / "scripts"
LOG_DIR = ECOS / "daemon-logs"
STATE_DB = ECOS / "daemon-state.db"
BRIEF_SCRIPT = SCRIPTS / "ecos-brief.py"
HEALTH_SCRIPT = SCRIPTS / "ecos-health-check.py"
SLA_SCRIPT = SCRIPTS / "ecos-sla-tracker.py"
CONSTRAINT_SCRIPT = Path.home() / "Documents" / "@学习进化" / "_knowledge" / "10-systems" / "基建架构" / "ecos-constraint-validator.py"
DIGEST_SCRIPT = SCRIPTS / "ecos-weekly-digest.py"
DIGEST_OUTPUT = DOCS / "@驾驶舱" / "_generated" / "CARDS" / "health-digest.md"
BRIEF_OUTPUT = DOCS / "@驾驶舱" / "brief.md"

INTERVAL = 21600  # 6h
WEEKLY_INTERVAL = 28  # 每 28 次 ≈ 7 天

running = True


def signal_handler(signum, frame):
    global running
    print(f"\n  ⏹️  收到信号 {signum}，优雅关闭...")
    running = False


def init_state():
    """初始化持久状态"""
    STATE_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(STATE_DB))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cycles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at TEXT NOT NULL,
            completed_at TEXT,
            exit_code INTEGER DEFAULT 0,
            summary TEXT DEFAULT ''
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cycle_id INTEGER,
            alert_type TEXT NOT NULL,
            message TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    conn.commit()
    return conn


def run_script(path: Path, args: list = None, timeout: int = 60) -> tuple[int, str]:
    """运行脚本，try/except 兜底"""
    if not path.exists():
        return 2, f"❌ 脚本缺失: {path}"
    cmd = ["python3", str(path)]
    if args:
        cmd.extend(args)
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, (r.stdout or "")[:2000]
    except subprocess.TimeoutExpired:
        return 1, "⚠️ 超时"
    except Exception as e:
        return 1, f"⚠️ 异常: {e}"


def run_cycle(conn: sqlite3.Connection, cycle_num: int) -> int:
    """执行一次完整检查周期"""
    now = datetime.now(timezone.utc)
    started = now.isoformat()

    cursor = conn.execute("INSERT INTO cycles (started_at) VALUES (?)", (started,))
    cycle_id = cursor.lastrowid
    conn.commit()

    print(f"\n{'='*56}")
    print(f"  周期 #{cycle_num} — {now.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*56}")

    errors = []

    # 0. 变更门禁 (mof-gate) — "动架构必须先改 L0"
    if (WORKSPACE / "projects" / "ecos" / "src" / "ecos" / "ssot" / "tools" / "mof-gate.py").exists():
        run_script(WORKSPACE / "projects" / "ecos" / "src" / "ecos" / "ssot" / "tools" / "mof-gate.py")

    # 0.1 L0 自举校验 (mof-bootstrap)
    if (WORKSPACE / "projects" / "ecos" / "src" / "ecos" / "ssot" / "tools" / "mof-bootstrap.py").exists():
        run_script(WORKSPACE / "projects" / "ecos" / "src" / "ecos" / "ssot" / "tools" / "mof-bootstrap.py")

    # 0.1 层合规强制扫描 (mof-enforce)
    if (WORKSPACE / "projects" / "ecos" / "src" / "ecos" / "ssot" / "tools" / "mof-enforce.py").exists():
        run_script(WORKSPACE / "projects" / "ecos" / "src" / "ecos" / "ssot" / "tools" / "mof-enforce.py", ["--no-cards"])

    # 0.2 SLA 执行 + M0 快照 (mof-sla)
    if (WORKSPACE / "projects" / "ecos" / "src" / "ecos" / "ssot" / "tools" / "mof-sla.py").exists():
        run_script(WORKSPACE / "projects" / "ecos" / "src" / "ecos" / "ssot" / "tools" / "mof-sla.py")

    # 1. L0 协议约束 + half_life (编译模式)
    print("\n── L0 协议约束 ──")
    compiler_script = SCRIPTS / "ecos-constraint-compiler.py"
    if compiler_script.exists() and compiler_script != CONSTRAINT_SCRIPT:
        code, out = run_script(compiler_script, timeout=15)
        for line in out.split("\n"):
            if "衰减" in line or "约束" in line:
                print(f"  {line.strip()}")
    else:
        code, out = run_script(CONSTRAINT_SCRIPT)
        for line in out.split("\n"):
            if "衰减" in line or "✅" in line and "X" in line:
                print(f"  {line.strip()}")
    if code != 0:
        errors.append(f"L0 约束: exit={code}")
        conn.execute("INSERT INTO alerts (cycle_id, alert_type, message, created_at) VALUES (?,?,?,?)",
                     (cycle_id, "L0_constraint", f"exit={code}", started))

    # 1.5 L3 入口深度统计
    profiler_script = SCRIPTS / "ecos-entry-profiler.py"
    if profiler_script.exists():
        run_script(profiler_script, ["--session-start"], timeout=5)

    # 2. 健康检查
    print("\n── 健康检查 ──")
    code, out = run_script(HEALTH_SCRIPT, ["--json"])
    try:
        data = json.loads(out)
        results = data.get("results", [])
        passed = sum(1 for r in results if r.get("pass") is True)
        failed = sum(1 for r in results if r.get("pass") is False)
        print(f"  {passed}/{passed+failed} 通过")
        if failed > 0:
            for r in results:
                if r.get("pass") is False:
                    reason = r.get("reason", "")[:60]
                    print(f"  ⚠️  {r['name']}: {reason}")
                    conn.execute(
                        "INSERT INTO alerts (cycle_id, alert_type, message, created_at) VALUES (?,?,?,?)",
                        (cycle_id, "health_check", f"{r['name']}: {reason}", started))
            errors.append(f"健康检查: {failed} 项失败")
    except (json.JSONDecodeError, KeyError):
        if code != 0:
            errors.append("健康检查: 解析失败")

    # 3. SLA 记录
    sla_result = "pass" if not errors else "fail"
    run_script(SLA_SCRIPT, ["--log", sla_result, "--dim", "daemon",
                            "--detail", f"cycle={cycle_num}"])

    # 3.5 存储空间检查
    disk_check = Path.home() / ".ecos" / "scripts" / "check-disk-usage.py"
    if disk_check.exists():
        code, out = run_script(disk_check, timeout=10)
        for line in out.split("\n"):
            if line.strip():
                print(f"  {line.strip()}")
        if code != 0:
            errors.append(f"存储: exit={code}")

    # 3.6 文件目录增量扫描 (每 4 周期 ≈ 24h)
    if cycle_num % 4 == 0:
        catalog = Path.home() / ".ecos" / "scripts" / "catalog-daemon.py"
        if catalog.exists():
            for vol in ["sharedmodel", "model"]:
                code, out = run_script(catalog, ["--update", vol, "--max-depth", "10", "--json"], timeout=120)
                print(f"  📁 catalog {vol}: {'✅' if code==0 else '⚠️'}")

    # 4. 周报 (每 WEEKLY_INTERVAL 次)
    if cycle_num % WEEKLY_INTERVAL == 0 and DIGEST_SCRIPT.exists():
        print("\n── 每周摘要 ──")
        code, out = run_script(DIGEST_SCRIPT, ["--output", str(DIGEST_OUTPUT)])
        if code == 0:
            print(f"  ✅ 已生成: {DIGEST_OUTPUT}")
        else:
            print(f"  ⚠️  生成失败: exit={code}")

    # 5. 会话简报更新
    if BRIEF_SCRIPT.exists():
        run_script(BRIEF_SCRIPT, ["--force", "--output", str(BRIEF_OUTPUT)],
                   timeout=45)

    # 2.7 自愈 (如果有错误)
    if errors:
        healer_script = SCRIPTS / "ecos-healer.py"
        if healer_script.exists():
            print("\n── 自治愈 ──")
            heal_code, heal_out = run_script(healer_script, ["--check-health"], timeout=30)
            for line in heal_out.split("\n"):
                if "→" in line:
                    print(f"  {line.strip()}")

    # 完成
    summary = "; ".join(errors) if errors else "全部通过"
    conn.execute("UPDATE cycles SET completed_at=?, exit_code=?, summary=? WHERE id=?",
                 (datetime.now(timezone.utc).isoformat(),
                  1 if errors else 0, summary, cycle_id))
    conn.commit()

    print(f"\n  结果: {'✅ 全部通过' if not errors else f'⚠️  {len(errors)} 项告警'}")
    print(f"{'='*56}")

    return 1 if errors else 0


def show_status(conn: sqlite3.Connection):
    """显示 daemon 状态"""
    print(f"\n{'='*56}")
    print(f"  eCOS Daemon — 状态报告")
    print(f"{'='*56}")

    cursor = conn.execute("SELECT COUNT(*), COALESCE(SUM(CASE WHEN exit_code=0 THEN 1 ELSE 0 END),0), "
                          "MAX(started_at) FROM cycles")
    total, passed, last = cursor.fetchone()
    print(f"\n  总周期: {total} 次")
    print(f"  通过: {passed} 次 ({passed/max(total,1)*100:.0f}%)")

    if last:
        print(f"  最近周期: {last[:19]}")

    cursor = conn.execute("SELECT alert_type, message, created_at FROM alerts "
                          "ORDER BY created_at DESC LIMIT 5")
    alerts = cursor.fetchall()
    if alerts:
        print(f"\n  最近告警 ({len(alerts)}):")
        for t, m, c in alerts:
            print(f"    {c[:16]} [{t}] {m[:80]}")

    cursor = conn.execute("SELECT COUNT(*) FROM alerts WHERE "
                          "created_at > datetime('now', '-24 hours')")
    recent_alerts = cursor.fetchone()[0]
    if recent_alerts == 0:
        print(f"\n  ✅ 过去 24h 内无告警")
    else:
        print(f"\n  ⚠️  过去 24h 内 {recent_alerts} 条告警")

    print()


def main():
    parser = argparse.ArgumentParser(description="eCOS v5 自治运维守护进程")
    parser.add_argument("--watch", action="store_true", help="持续监听模式")
    parser.add_argument("--status", action="store_true", help="查看状态")
    parser.add_argument("--once", action="store_true", help="单次运行")
    args = parser.parse_args()

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    conn = init_state()

    if args.status:
        show_status(conn)
        conn.close()
        return

    if args.watch:
        print(f"  eCOS Daemon v3.0 — 持续监听模式")
        print(f"  间隔: {INTERVAL}s (6h)")
        cycle_num = 0
        while running:
            cycle_num += 1
            run_cycle(conn, cycle_num)
            if running and cycle_num < 999:
                next_time = datetime.now() + timedelta(seconds=INTERVAL)
                print(f"\n  下一周期: {next_time.strftime('%Y-%m-%d %H:%M:%S')}")
                for i in range(INTERVAL):
                    if not running:
                        break
                    time.sleep(1)
        conn.close()
        print("  Daemon 已停止")
        return

    # 单次运行 (默认 / launchd 模式)
    cursor = conn.execute("SELECT COALESCE(MAX(id),0) FROM cycles")
    cycle_num = cursor.fetchone()[0] + 1
    exit_code = run_cycle(conn, cycle_num)
    conn.close()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
