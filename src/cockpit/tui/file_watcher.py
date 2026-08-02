"""
cockpit.tui.file_watcher — TUI 后台文件与状态监控 Worker (Phase 2)

特性:
  · 监控 .omo/state 目录或数据库存储状态
  · 当底层信息库或卡片数据变动时，向 Textual App 发送 DataChanged 信号
  · 极致优雅降级：若目录不存在或 watchfiles 无法启动，不报错、不崩溃
"""

from __future__ import annotations

import logging
import os
from collections.abc import Callable
from pathlib import Path

logger = logging.getLogger(__name__)


def is_watcher_supported() -> bool:
    """检查是否能够运行异步 watchfiles."""
    try:
        import watchfiles

        return True
    except ImportError:
        return False


def get_default_watch_dir() -> Path | None:
    """定位值得监控的状态根路径."""
    possible_paths = [
        Path.cwd() / ".omo" / "state",
        Path.home() / ".omo" / "state",
        Path.cwd() / ".omo",
    ]
    for p in possible_paths:
        if p.exists() and p.is_dir():
            return p
    return None


def watch_state_directory(callback: Callable[[], None], watch_dir: Path | None = None) -> None:
    """后台任务运行函数：当被监测的路径改变时触发回调.

    仅被设计为运行在 Textual @work(thread=True) 线程中。
    """
    if not is_watcher_supported():
        logger.debug("watchfiles dependency missing, TUI state watch disabled.")
        return

    import watchfiles

    target = watch_dir or get_default_watch_dir()
    if not target or not target.exists():
        logger.debug("No valid watch directory found for TUI state watch.")
        return

    logger.debug("TUI watching state directory: %s", target)
    try:
        for _changes in watchfiles.watch(target, raise_interrupt=False):
            # 执行 UI 重绘通知回调
            try:
                callback()
            except Exception as e:
                logger.debug("TUI watch callback error: %s", e)
    except Exception as e:
        logger.debug("watchfiles monitor terminated: %s", e)
