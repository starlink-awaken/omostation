"""命令: watch — 文件监听自动重推导"""

from ontoderive.watcher import FileWatcher


def cmd_watch(project: str = ".", interval: int = 5) -> None:
    """文件监听自动重推导"""
    w = FileWatcher(project)
    print(f"[watch] 监听中... 间隔{interval}秒, Ctrl+C停止")
    w.watch(interval=interval, auto_run=True)
