#!/usr/bin/env python3
"""
eCOS v5 L3 — 入口深度统计 (ecos-entry-profiler)
===================================================
Phase 8.2 / v5 能力补全
自动记录 Agent 每次会话的入口行为:
  - 读取了哪些文件
  - 以什么顺序读取
  - 执行了哪些命令
  - 耗时分布

用法:
    python3 ecos-entry-profiler.py --session-start   # 标记会话开始
    python3 ecos-entry-profiler.py --read FILE       # 记录一次文件读取
    python3 ecos-entry-profiler.py --cmd "CMD"       # 记录一次命令执行
    python3 ecos-entry-profiler.py --session-end     # 标记会话结束
    python3 ecos-entry-profiler.py --report          # 生成深度统计报告
    python3 ecos-entry-profiler.py --watch           # 连续监听
"""

import sys
import json
import argparse
import subprocess
import time
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from collections import Counter, defaultdict


SESSION_DIR = Path.home() / ".ecos" / "sessions"
EVENT_FILE = Path.home() / ".ecos" / "events" / "entry-stream.jsonl"
ENTRY_PATTERNS = [
    "CLAUDE_COWORK_GLOBAL.md",
    "CLAUDE.md", "claude.md",
    "DASHBOARD.md",
    "brief.md",
    "OPS.md",
    "ONBOARD.md",
    "ACCESS.md",
]


def get_session_id() -> str:
    """获取当前会话 ID"""
    SESSION_DIR.mkdir(parents=True, exist_ok=True)
    sid_file = SESSION_DIR / "current.txt"
    if sid_file.exists():
        sid = sid_file.read_text().strip()
        # 检查会话是否过期 (> 24h)
        parts = sid.split("-")
        if len(parts) >= 2:
            try:
                ts = datetime.strptime(parts[-1], "%Y%m%d%H%M%S")
                if (datetime.now() - ts).total_seconds() < 86400:
                    return sid
            except ValueError:
                pass
    return ""


def new_session_id() -> str:
    now = datetime.now()
    sid = f"session-{now.strftime('%Y%m%d%H%M%S')}-{os.getpid()}"
    SESSION_DIR.mkdir(parents=True, exist_ok=True)
    (SESSION_DIR / "current.txt").write_text(sid)
    return sid


def write_event(event: dict):
    """写入事件流"""
    EVENT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(EVENT_FILE, "a") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def read_events(hours: int = 72) -> list[dict]:
    """读取最近事件"""
    if not EVENT_FILE.exists():
        return []
    cutoff = datetime.now() - timedelta(hours=hours)
    events = []
    with open(EVENT_FILE, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                evt = json.loads(line)
                ts = evt.get("timestamp", "")
                if ts and ts[:19] >= cutoff.strftime("%Y-%m-%dT%H:%M"):
                    events.append(evt)
            except json.JSONDecodeError:
                continue
    return events


def session_start() -> dict:
    sid = new_session_id()
    event = {
        "type": "session.start",
        "session_id": sid,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    write_event(event)
    print(f"  ✅ 会话已标记: {sid}")
    return event


def session_end() -> dict:
    sid = get_session_id()
    event = {
        "type": "session.end",
        "session_id": sid or "unknown",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    write_event(event)
    print(f"  ✅ 会话结束: {sid}")
    return event


def record_read(filepath: str) -> dict:
    """记录文件读取"""
    fname = Path(filepath).name
    entry_type = "entry_file" if any(p in filepath for p in ENTRY_PATTERNS) else "domain_file"
    event = {
        "type": "file.read",
        "session_id": get_session_id() or new_session_id(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "file": fname,
        "path": filepath[:120],
        "entry_type": entry_type,
    }
    write_event(event)
    return event


def record_cmd(command: str, duration_ms: int = 0) -> dict:
    """记录命令执行"""
    event = {
        "type": "cmd.exec",
        "session_id": get_session_id() or new_session_id(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "command": command[:100],
        "duration_ms": duration_ms,
    }
    write_event(event)
    return event


def generate_report(events: list[dict]) -> str:
    """生成入口深度统计报告"""
    lines = []
    lines.append("=" * 60)
    lines.append("  eCOS v5 L3 — 入口深度统计报告")
    lines.append("=" * 60)

    if not events:
        lines.append("\n 暂无会话数据 — 运行 `ecos-entry-profiler.py --session-start` 开始记录\n")
        return "\n".join(lines)

    # 按类型分类
    sessions = [e for e in events if e["type"] == "session.start"]
    file_reads = [e for e in events if e["type"] == "file.read"]
    cmd_execs = [e for e in events if e["type"] == "cmd.exec"]
    sessions_ended = [e for e in events if e["type"] == "session.end"]

    lines.append(f"\n  📊 总览")
    lines.append(f"  会话: {len(sessions)} 次")
    lines.append(f"  文件读取: {len(file_reads)} 次")
    lines.append(f"  命令执行: {len(cmd_execs)} 次")
    lines.append(f"  已结束: {len(sessions_ended)} 次")

    # 入口文件频率
    if file_reads:
        lines.append(f"\n  📖 入口文件频率")
        entry_files = [f["file"] for f in file_reads if f.get("entry_type") == "entry_file"]
        by_file = Counter(entry_files)
        for fname, count in by_file.most_common(10):
            bar = "█" * count + "░" * (10 - min(count, 10))
            lines.append(f"  {fname:30s} {count:3d} 次 {bar}")

    # 启动链顺序分析
    if sessions:
        lines.append(f"\n  🔗 启动链")
        for s in sessions[:5]:
            sid = s["session_id"]
            session_reads = [e for e in file_reads if e.get("session_id") == sid]
            chain = " → ".join([f.get("file", "?")[:20] for f in session_reads[:5]])
            if chain:
                lines.append(f"  {sid[:20]}... {chain}")

    # 命令分布
    if cmd_execs:
        lines.append(f"\n  ⌨️  常用命令")
        by_cmd = Counter(c["command"][:30] for c in cmd_execs)
        for cmd_name, count in by_cmd.most_common(8):
            lines.append(f"  {cmd_name:30s} {count:3d} 次")

    # 活跃时段
    timestamps = [
        datetime.fromisoformat(e["timestamp"].replace("Z", "+00:00"))
        for e in events if e.get("timestamp")
    ]
    if timestamps:
        span = (max(timestamps) - min(timestamps)).total_seconds() / 3600
        lines.append(f"\n  ⏱️  追踪时段: {span:.1f} 小时")
        lines.append(f"  最早: {min(timestamps).strftime('%m-%d %H:%M')}")
        lines.append(f"  最晚: {max(timestamps).strftime('%m-%d %H:%M')}")

    lines.append(f"\n{'='*60}")
    return "\n".join(lines)


def watch_mode():
    """连续监听并记录"""
    import signal
    running = True

    def handler(signum, frame):
        nonlocal running
        running = False

    signal.signal(signal.SIGTERM, handler)
    signal.signal(signal.SIGINT, handler)

    sid = new_session_id()
    print(f"  L3 入口深度统计 — 监听中 (session={sid[:20]}...)")
    print(f"  按 Ctrl+C 停止\n")

    try:
        while running:
            # 模拟检测 Agent 文件读取 (通过 lsof 或 fswatch)
            time.sleep(10)
    except KeyboardInterrupt:
        pass
    finally:
        session_end()


def main():
    parser = argparse.ArgumentParser(description="eCOS v5 L3 入口深度统计")
    parser.add_argument("--session-start", action="store_true", help="标记会话开始")
    parser.add_argument("--session-end", action="store_true", help="标记会话结束")
    parser.add_argument("--read", type=str, help="记录文件读取")
    parser.add_argument("--cmd", type=str, nargs=2, metavar=("CMD", "DURATION_MS"), help="记录命令执行")
    parser.add_argument("--report", action="store_true", help="生成深度统计报告")
    parser.add_argument("--watch", action="store_true", help="连续监听")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    args = parser.parse_args()

    if args.session_start:
        r = session_start()
        if args.json: print(json.dumps(r, indent=2))
        return

    if args.session_end:
        r = session_end()
        if args.json: print(json.dumps(r, indent=2))
        return

    if args.read:
        r = record_read(args.read)
        if args.json: print(json.dumps(r, indent=2))
        return

    if args.cmd:
        cmd, duration = args.cmd
        r = record_cmd(cmd, int(duration))
        if args.json: print(json.dumps(r, indent=2))
        return

    if args.watch:
        watch_mode()
        return

    events = read_events(72)
    if args.json:
        print(json.dumps(events, ensure_ascii=False, indent=2))
    else:
        print(generate_report(events))


if __name__ == "__main__":
    main()
