#!/usr/bin/env python3
# ruff: noqa
"""
KOS File Watcher — 文件系统实时监控

实时监控文件变更并触发增量索引。

Usage:
    from kos.maintenance.watcher import FileWatcher

    watcher = FileWatcher()
    watcher.start()  # Blocking

    # Or via CLI:
    # kos index --watch
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from typing import Any

from kos.config import get_workspace_manifest
from kos.maintenance.indexer import IncrementalIndexer


class FileWatcher:
    """文件系统变更监控器。

    使用轮询方式检测文件变更 (跨平台兼容)。
    对于 macOS/Linux 可使用 fsevents/inotify 进一步优化。
    """

    def __init__(self, poll_interval: float = 60.0):
        """
        Args:
            poll_interval: 轮询间隔 (秒)
        """
        self.poll_interval = poll_interval
        self._running = False
        self._indexer = IncrementalIndexer()
        self._snapshot: dict[str, float] = {}  # path -> mtime

    def start(self):
        """启动监控 (阻塞)。"""
        self._running = True
        print(f"Watching for file changes (poll interval: {self.poll_interval}s)...")
        print("Press Ctrl+C to stop.")
        sys.stdout.flush()

        # Initial scan
        self._full_scan()

        try:
            while self._running:
                time.sleep(self.poll_interval)
                self._check_changes()
        except KeyboardInterrupt:
            print("\nStopping watcher...")
        finally:
            self.stop()

    def stop(self):
        """停止监控。"""
        self._running = False
        self._indexer.close()

    def _full_scan(self):
        """完整扫描所有域。"""
        zones = self._indexer._get_zones()
        for zone_id, zone_config in zones.items():
            scan_path = zone_config.get("path", "")
            if not scan_path:
                continue
            p = Path(scan_path).expanduser()
            if p.exists():
                for f in p.rglob("*"):
                    if f.is_file():
                        self._snapshot[str(f)] = f.stat().st_mtime

    def _check_changes(self):
        """检测文件变更。"""
        changed = False
        zones = self._indexer._get_zones()

        for zone_id, zone_config in zones.items():
            scan_path = zone_config.get("path", "")
            if not scan_path:
                continue
            p = Path(scan_path).expanduser()
            if not p.exists():
                continue

            current_files: dict[str, float] = {}
            for f in p.rglob("*"):
                if f.is_file():
                    fpath = str(f)
                    mtime = f.stat().st_mtime
                    current_files[fpath] = mtime

                    # Check for new or modified files
                    if fpath not in self._snapshot or self._snapshot[fpath] != mtime:
                        changed = True
                        print(f"  Changed: {fpath}")

            # Check for deleted files
            for old_path in self._snapshot:
                if old_path.startswith(str(p)) and old_path not in current_files:
                    changed = True
                    print(f"  Deleted: {old_path}")

        # Update snapshot
        self._full_scan()

        # Run incremental indexer if changes detected
        if changed:
            print("Changes detected, running incremental index...")
            sys.stdout.flush()
            result = self._indexer.run(embed=False)
            print(f"Indexed: +{result['added']} new, ~{result['updated']} updated", flush=True)


# ── CLI 入口 ──────────────────────────────────────────────


def main():
    import argparse

    parser = argparse.ArgumentParser(description="KOS File Watcher")
    parser.add_argument("--interval", type=float, default=60.0, help="Polling interval in seconds (default: 60)")
    args = parser.parse_args()

    watcher = FileWatcher(poll_interval=args.interval)
    watcher.start()


if __name__ == "__main__":
    main()
