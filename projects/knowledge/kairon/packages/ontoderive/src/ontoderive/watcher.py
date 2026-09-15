"""
OntoDerive 文件监听器 — 变化检测 + 自动重推导
==============================================
当facts/entities/inferences/scheme任一文件变化时，自动重新执行推导+检查。

用法:
    python3 engine/watcher.py --project . --interval 5
    python3 engine/watcher.py --project . --auto-derive-check
"""

import hashlib
import subprocess
import time
from pathlib import Path
from typing import Any


class FileWatcher:
    def __init__(self, project_root: Any, watch_dirs: Any = None) -> None:
        self.root = Path(project_root)
        self.watch_dirs = watch_dirs or ["facts", "entities", "inferences", "scheme"]
        self.hashes: dict[Any, Any] = {}
        self._snapshot()

    def _snapshot(self) -> None:
        """记录当前所有文件哈希"""
        self.hashes = {}
        for d in self.watch_dirs:
            dp = self.root / d
            if not dp.exists():
                continue
            for f in sorted(dp.rglob("*")):
                if f.is_file():
                    self.hashes[str(f.relative_to(self.root))] = self._hash(f)

    def _hash(self, filepath: Any) -> Any:
        try:
            return hashlib.md5(Path(filepath).read_bytes()).hexdigest()  # noqa: S324
        except OSError:
            return ""

    def check(self) -> Any:
        """检查是否有文件变化，返回变化列表"""
        changes = []
        for d in self.watch_dirs:
            dp = self.root / d
            if not dp.exists():
                continue
            for f in sorted(dp.rglob("*")):
                if f.is_file():
                    rel = str(f.relative_to(self.root))
                    new_hash = self._hash(f)
                    if rel not in self.hashes:
                        changes.append(("added", rel))
                    elif self.hashes[rel] != new_hash:
                        changes.append(("modified", rel))
        # 检测删除
        for old_file in list(self.hashes.keys()):
            if not (self.root / old_file).exists():
                changes.append(("removed", old_file))
        self._snapshot()
        return changes

    def watch(self, interval: Any = 5, auto_run: Any = True) -> None:
        """持续监听，检测到变化时自动执行推导和检查"""
        print(f"[watcher] 👀 监听中... (间隔{interval}秒, 目录: {self.watch_dirs})")
        print("[watcher]   按 Ctrl+C 停止")
        round_num = 0
        try:
            while True:
                time.sleep(interval)
                changes = self.check()
                if changes:
                    round_num += 1
                    print(f"\n[watcher] 🔄 Round {round_num} — {len(changes)} file(s) changed:")
                    for change_type, filename in changes:
                        print(f"  {change_type:8s} {filename}")

                    if auto_run:
                        result = subprocess.run(
                            ["python3", "engine/derive.py", "--project", str(self.root), "--derive", "--check"],
                            capture_output=True,
                            text=True,
                        )
                        # 输出摘要
                        for line in result.stdout.split("\n"):
                            if "📊" in line or "✅" in line or "🟠" in line or "🟡" in line or "🔴" in line:
                                print(f"  {line.strip()}")
        except KeyboardInterrupt:
            print(f"\n[watcher] 🛑 停止监听。共检测 {round_num} 轮变化。")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="OntoDerive 文件监听器")
    parser.add_argument("--project", default=".", help="项目路径")
    parser.add_argument("--interval", type=int, default=5, help="检测间隔(秒)")
    parser.add_argument("--auto-derive-check", action="store_true", default=True)
    args = parser.parse_args()

    watcher = FileWatcher(args.project)
    watcher.watch(interval=args.interval, auto_run=args.auto_derive_check)
