#!/usr/bin/env python3
"""
eCOS v5 L1 — 事件驱动保鲜 (ecos-event-watcher)
=================================================
Phase 8.2 / v5 能力补全
替代 cron-based daemon 检查 — 当文件变更时自动触发保鲜。
使用 fswatch (macOS) 监听文件系统事件。

用法:
    python3 ecos-event-watcher.py                    # 启动监听 (前台)
    python3 ecos-event-watcher.py --daemon           # 后台 daemon 模式
    python3 ecos-event-watcher.py --once             # 单次扫描 (不监听)

依赖:
    - fswatch (brew install fswatch)
    - 降级: watchdog (pip install watchdog)
"""

import sys
import json
import subprocess
import time
import os
import signal
from datetime import datetime, timezone
from pathlib import Path


# ── 路径 ──
DOCS = Path.home() / "Documents"
SCRIPTS = DOCS / "驾驶舱" / "scripts"
LOG_DIR = DOCS / "驾驶舱" / "CARDS" / "watcher-logs"
STATE_FILE = Path.home() / ".ecos" / "watcher-state.json"

# 监听的文件模式
WATCH_PATTERNS = [
    "**/CLAUDE.md",
    "**/STATE.md",
    "**/claude.md",
    "**/DASHBOARD.md",
    "**/SIGNALS.md",
]

# 静默期 (秒) — 文件变更后等待多久再触发
DEBOUNCE_SECONDS = 10

running = True


def signal_handler(signum, frame):
    global running
    print(f"\n  ⏹️  收到信号 {signum}，停止监听...")
    running = False


def trigger_freshness(changed_file: str):
    """文件变更时触发保鲜检查"""
    now = datetime.now(timezone.utc)

    # 1. 记录事件
    event = {
        "timestamp": now.isoformat(),
        "file": changed_file,
        "action": "modified",
    }
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    events = []
    if STATE_FILE.exists():
        with open(STATE_FILE, "r") as f:
            try:
                events = json.loads(f.read())
            except json.JSONDecodeError:
                events = []
    events.append(event)
    events = events[-100:]  # 保留最近 100 条
    STATE_FILE.write_text(json.dumps(events, ensure_ascii=False, indent=2))

    # 2. 触发 CLAUDE.md 保鲜 (如果变更的是 CLAUDE.md)
    if "CLAUDE.md" in changed_file or "claude.md" in changed_file:
        freshness_script = SCRIPTS / "check-claude-freshness.py"
        if freshness_script.exists():
            subprocess.run(
                ["python3", str(freshness_script),
                 "--root", str(DOCS), "--max-age-days", "60", "--json"],
                capture_output=True, text=True, timeout=15,
            )

    # 3. 更新事件流
    event_file = Path.home() / ".ecos" / "events" / "event-stream.jsonl"
    event_file.parent.mkdir(parents=True, exist_ok=True)
    event_record = {
        "type": "freshness.trigger",
        "source": "event-watcher",
        "timestamp": now.isoformat(),
        "payload": {"file": changed_file},
    }
    with open(event_file, "a") as f:
        f.write(json.dumps(event_record, ensure_ascii=False) + "\n")

    print(f"  [{now.strftime('%H:%M:%S')}] 🔄 {Path(changed_file).name} → 保鲜触发")


def watch_fswatch():
    """使用 fswatch 监听"""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    print(f"  L1 事件保鲜 — fswatch 监听中")
    print(f"  目录: {DOCS}")
    print(f"  静默: {DEBOUNCE_SECONDS}s\n")

    try:
        # 构建 fswatch 命令
        cmd = [
            "fswatch", "-0",
            "--event", "Updated",
            "--latency", str(DEBOUNCE_SECONDS),
            "--recursive",
            str(DOCS / "驾驶舱"),
            str(DOCS / "学习进化"),
            str(DOCS / "工作文档"),
            str(DOCS / "家庭生活"),
        ]

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )

        while running:
            try:
                output = process.stdout.read(4096) if process.stdout else ""
                if not output:
                    break
                for filepath in output.split("\0"):
                    filepath = filepath.strip()
                    if not filepath:
                        continue
                    # 过滤感兴趣的文件
                    if any(p in filepath for p in ["CLAUDE.md", "claude.md", "STATE.md"]):
                        trigger_freshness(filepath)
            except (IOError, OSError):
                break

        process.terminate()
        process.wait()

    except FileNotFoundError:
        print("  ⚠️  fswatch 未安装。尝试 watchdog 降级...\n")
        watch_watchdog()


def watch_watchdog():
    """降级方案: watchdog Python 库"""
    try:
        from watchdog.observers import Observer
        from watchdog.events import FileSystemEventHandler
    except ImportError:
        print("  ❌ fswatch 和 watchdog 均不可用。")
        print("     安装: brew install fswatch  或  pip install watchdog")
        return

    class FreshnessHandler(FileSystemEventHandler):
        def on_modified(self, event):
            if event.is_directory:
                return
            src_path = event.src_path
            if any(p in src_path for p in ["CLAUDE.md", "claude.md", "STATE.md"]):
                trigger_freshness(src_path)

    event_handler = FreshnessHandler()
    observer = Observer()
    observer.schedule(event_handler, str(DOCS), recursive=True)
    observer.start()

    print(f"  L1 事件保鲜 — watchdog 监听中")
    print(f"  目录: {DOCS}")
    print(f"  静默: {DEBOUNCE_SECONDS}s\n")

    try:
        while running:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()


def once_scan():
    """单次扫描所有文件"""
    print(f"  L1 事件保鲜 — 单次扫描\n")
    fresh_count = 0
    stale_count = 0

    for pattern in WATCH_PATTERNS:
        for f in DOCS.glob(pattern):
            if f.is_file() and not f.is_symlink():
                mtime = datetime.fromtimestamp(f.stat().st_mtime)
                age = (datetime.now() - mtime).days
                if age > 60:
                    print(f"  ⚠️  过期: {f.name} ({age}d)")
                    stale_count += 1
                else:
                    fresh_count += 1

    print(f"\n  结果: {fresh_count} 新鲜, {stale_count} 过期")
    return stale_count


def main():
    import argparse
    parser = argparse.ArgumentParser(description="eCOS v5 L1 事件驱动保鲜")
    parser.add_argument("--daemon", action="store_true", help="后台 daemon 模式")
    parser.add_argument("--once", action="store_true", help="单次扫描")
    args = parser.parse_args()

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    if args.once:
        sys.exit(once_scan())

    if args.daemon:
        pid = os.fork()
        if pid > 0:
            print(f"  Daemon 已启动 (PID: {pid})")
            sys.exit(0)
        os.setsid()

    watch_fswatch()


if __name__ == "__main__":
    main()
