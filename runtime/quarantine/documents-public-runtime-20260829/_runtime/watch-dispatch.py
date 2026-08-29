#!/usr/bin/env python3
"""watch-dispatch.py — 分钟级变更调度器（cron 通道版事件驱动）

背景 (2026-07-03): launchd WatchPaths 方案受 macOS TCC 限制——python 的权限
归因是框架内部 Python.app，FDA 面板拖 python3/python3.9 均不生效；而 cron
通道已验证有完全磁盘访问。故改为 cron 每分钟运行本调度器：扫描被监视路径
的最新 mtime，与上次戳记比较，有变更才触发对应生成器（无变更零成本退出）。

延迟: ≤60s（配合 l4-kernel/ecos pre-commit 的提交时即时拦截，源头已是 0 延迟）。
戳记: ~/Workspace/runtime/.watch-dispatch-stamps.json
crontab: * * * * * /usr/bin/python3 <本文件> >> governance-cron.log 2>&1
v1.0 | 2026-07-03
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

DOCS_ROOT = Path(__file__).resolve().parents[2]
WS_ROOT = Path(os.environ.get("WORKSPACE_ROOT", DOCS_ROOT.parent / "Workspace"))
RUNTIME = DOCS_ROOT / "@公共/_runtime"
STAMPS = WS_ROOT / "runtime/.watch-dispatch-stamps.json"


def manifest_watch_paths() -> list[Path]:
    """Watch the Documents authority, not the retired global registry/MOF view."""

    paths = [DOCS_ROOT / "@公共/_control/L4-DOMAIN-REGISTRY.yaml"]
    paths.extend(DOCS_ROOT.glob("@*/DOMAIN.yaml"))
    paths.extend((DOCS_ROOT / "@工作文档").glob("*/DOMAIN.yaml"))
    return paths


# 监视组: (组名, [监视路径], [触发命令 argv])
WATCHES = [
    (
        "domain-manifests",
        manifest_watch_paths(),
        [sys.executable, str(RUNTIME / "domain-sync.py"), "--write"],
    ),
    ("workspace-state",
     [WS_ROOT / ".omo/state", WS_ROOT / "data/cards/cards.db"],
     [sys.executable, str(RUNTIME / "bridge-refresh.py")]),
    ("inbox-router",
     [DOCS_ROOT / "_inbox"],
     [sys.executable, str(RUNTIME / "session-brief.py")]),
    ("weekly-verdict",
     [WS_ROOT / "data/cards/cards.db"],
     [sys.executable, str(RUNTIME / "weekly-verdict-generator.py")]),
]


def latest_mtime(paths: list[Path]) -> float:
    m = 0.0
    for p in paths:
        if p.is_file():
            m = max(m, p.stat().st_mtime)
        elif p.is_dir():
            for f in p.rglob("*"):
                if f.is_file() and "__pycache__" not in f.parts:
                    m = max(m, f.stat().st_mtime)
    return m


def main() -> int:
    try:
        stamps = json.loads(STAMPS.read_text()) if STAMPS.exists() else {}
    except json.JSONDecodeError:
        stamps = {}
    fired = []
    for name, paths, cmd in WATCHES:
        cur = latest_mtime(paths)
        if cur > stamps.get(name, 0.0):
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=120,
                               env={**os.environ, "WORKSPACE_ROOT": str(WS_ROOT)})
            ts = datetime.now(timezone.utc).strftime("%m-%d %H:%M:%S")
            tail = (r.stdout.strip().splitlines() or ["(无输出)"])[-1]
            print(f"[watch-dispatch {ts}] {name} 变更 → {cmd[1].split('/')[-1]}: {tail}"
                  + ("" if r.returncode == 0 else f" ⚠️ exit={r.returncode} {r.stderr.strip()[:200]}"))
            stamps[name] = cur
            fired.append(name)
    if fired:
        STAMPS.parent.mkdir(parents=True, exist_ok=True)
        STAMPS.write_text(json.dumps(stamps))
    return 0


if __name__ == "__main__":
    sys.exit(main())
