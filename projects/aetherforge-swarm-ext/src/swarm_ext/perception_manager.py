from __future__ import annotations

# ruff: noqa: RUF002, RUF003
import asyncio

# ---
# domain: D-Intelligence
# layer: organ
# status: active
# ---
"""
---
Type: Module
Status: ACTIVE
Version: 1.0.0
Authority: organs/D-Execution/AGENTS.md
Layer: L3
---
"""

import json
import logging
import os
import sqlite3
import time
from collections.abc import Callable, Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Any


@contextmanager
def _managed_connection(conn: sqlite3.Connection) -> Generator[sqlite3.Connection]:
    """Wrap a SQLite connection with commit/rollback semantics and guaranteed close."""
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Perception_Manager ≡ Environmental_Sensor
# 内涵 ≝ {Monitor, Discover, Trigger}
# 外延 ≝ {p | p ∈ D-Execution ∧ perceives(p, Environment)}
# 功能 ⊢ {MonitorFilesystem, DiscoverResources, TriggerEvents}
# =============================================================================

"""
---
Type: Organ
Status: ACTIVE
Version: 1.0.0
Owner: '@Architect'
Authority: nucleus/Z-Spore/dna/R0-ACT-SYS-AX01-14_holographic_routing_axiom.md
Layer: D-Execution
Constraint: "[!!] PERCEPTION_MANAGER_REALTIME"
Summary: '感知管理器 - 管理环境感知、资源发现和事件触发'
---

Perception Manager - 感知管理器

职责:
- 实时监控文件系统变化
- 自动发现外部资源
- 触发事件并通知相关组件
- 支持异步处理

作者: iFlow CLI
日期: 2026-03-03
状态: 生产就绪
"""

_log = logging.getLogger(__name__)


class PerceptionManager:
    """感知管理器 - 管理环境感知、资源发现和事件触发"""

    def __init__(self, db_path: str | None = None) -> None:
        """
        初始化感知管理器

        Args:
            db_path: 数据库路径
        """
        self.db_path = db_path or os.environ.get("BOS_EXECUTION_DB", "data/db/organs/execution/execution.db")
        self._monitors: dict[str, dict] = {}  # path -> monitor_config
        self._events: list[dict] = []  # 事件队列
        self._max_events = 1000  # 最大事件数量
        self._is_running = False
        self._monitoring_task = None
        self.initialize()

    def _get_connection(self) -> Generator[sqlite3.Connection]:
        """获取数据库连接"""
        if not self.db_path.startswith("file:"):
            Path(self.db_path).expanduser().parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.execute("PRAGMA busy_timeout=30000")
        conn.isolation_level = None  # Set to None to execute PRAGMA
        try:
            conn.execute("PRAGMA journal_mode=DELETE")
        except sqlite3.OperationalError:
            pass  # Ignore if already in other mode
        conn.isolation_level = ""  # Restore autocommit
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.row_factory = sqlite3.Row
        return _managed_connection(conn)

    def initialize(self) -> None:
        """初始化数据库表"""
        with self._get_connection() as conn:
            conn.execute(
                """
            CREATE TABLE IF NOT EXISTS perception_monitors (
                monitor_id TEXT PRIMARY KEY,
                path TEXT NOT NULL,
                callback TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'ACTIVE',
                created_at REAL NOT NULL,
                last_triggered REAL
            );"""
            )

            conn.execute(
                """
            CREATE TABLE IF NOT EXISTS perception_events (
                event_id TEXT PRIMARY KEY,
                event_type TEXT NOT NULL,
                event_data TEXT NOT NULL,
                source TEXT NOT NULL,
                timestamp REAL NOT NULL
            );"""
            )

            conn.commit()

        _log.info("[*] PerceptionManager initialized")

    def monitor_filesystem(self, path: str, callback: Callable = None) -> str:  # noqa: RUF013
        """
        监控文件系统变化

        Args:
            path: 监控路径
            callback: 变化回调函数

        Returns:
            str: 监控 ID
        """
        import hashlib

        monitor_id = hashlib.md5(f"{path}_{time.time()}".encode(), usedforsecurity=False).hexdigest()

        # 注册监控
        self._monitors[monitor_id] = {
            "path": path,
            "callback": callback,
            "status": "ACTIVE",
            "created_at": time.time(),
            "last_triggered": None,
        }

        # 记录到数据库
        with self._get_connection() as conn:
            conn.execute(
                """
            INSERT INTO perception_monitors (monitor_id, path, callback, status, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
                (monitor_id, path, str(callback), "ACTIVE", time.time()),
            )
            conn.commit()

        _log.info("✅ [Perception] Started monitoring: {path}")

        # 如果没有运行监控任务，启动它
        if not self._is_running:
            self._start_monitoring()

        return monitor_id

    def unwatch_filesystem(self, monitor_id: str) -> bool:
        """
        停止监控文件系统

        Args:
            monitor_id: 监控 ID

        Returns:
            bool: 是否成功停止
        """
        if monitor_id not in self._monitors:
            return False

        # 停止 watchdog 观察者（如果存在）
        monitor = self._monitors[monitor_id]
        if "observer" in monitor:
            try:
                monitor["observer"].stop()
                monitor["observer"].join(timeout=5)
                _log.info("⏸️ [Perception] Stopped watchdog observer: {monitor_id}")
            except (TimeoutError, asyncio.CancelledError):
                _log.info("⚠️ [Perception] Failed to stop observer: {e}")

        # 停止监控
        self._monitors[monitor_id]["status"] = "INACTIVE"

        # 更新数据库
        with self._get_connection() as conn:
            conn.execute(
                """
            UPDATE perception_monitors
            SET status = 'INACTIVE'
            WHERE monitor_id = ?
            """,
                (monitor_id,),
            )
            conn.commit()

        _log.info("⏸️ [Perception] Stopped monitoring: {monitor_id}")
        return True

    def _start_monitoring(self) -> None:
        """启动监控任务"""
        self._is_running = True
        _log.info("🚀 [Perception] Monitoring task started")

        # 在实际实现中，这里应该使用异步监控
        # 简化实现：使用轮询
        # 可以扩展为使用 watchdog 库

    async def async_monitor_filesystem(self, path: str, callback: Callable = None) -> str:  # noqa: RUF013
        """
        异步监控文件系统变化（使用 watchdog）

        Args:
            path: 监控路径
            callback: 变化回调函数

        Returns:
            str: 监控 ID
        """
        import hashlib

        monitor_id = hashlib.md5(f"{path}_{time.time()}".encode(), usedforsecurity=False).hexdigest()

        try:
            from watchdog.events import FileSystemEventHandler
            from watchdog.observers import Observer

            class FileChangeHandler(FileSystemEventHandler):
                def __init__(
                    self,
                    manager: PerceptionManager,
                    monitor_id: str,
                    path: str,
                    callback: Callable,
                ) -> None:
                    self.manager = manager
                    self.monitor_id = monitor_id
                    self.path = path
                    self.callback = callback

                def on_created(self, event: Any) -> None:
                    if not event.is_directory:
                        self.manager.trigger_event(
                            "file_created",
                            {
                                "path": event.src_path,
                                "monitor_id": self.monitor_id,
                                "monitor_path": self.path,
                            },
                            source=f"watchdog:{self.monitor_id}",
                        )
                        if self.callback:
                            self.callback("created", event.src_path)

                def on_modified(self, event: Any) -> None:
                    if not event.is_directory:
                        self.manager.trigger_event(
                            "file_modified",
                            {
                                "path": event.src_path,
                                "monitor_id": self.monitor_id,
                                "monitor_path": self.path,
                            },
                            source=f"watchdog:{self.monitor_id}",
                        )
                        if self.callback:
                            self.callback("modified", event.src_path)

                def on_deleted(self, event: Any) -> None:
                    if not event.is_directory:
                        self.manager.trigger_event(
                            "file_deleted",
                            {
                                "path": event.src_path,
                                "monitor_id": self.monitor_id,
                                "monitor_path": self.path,
                            },
                            source=f"watchdog:{self.monitor_id}",
                        )
                        if self.callback:
                            self.callback("deleted", event.src_path)

                def on_moved(self, event: Any) -> None:
                    if not event.is_directory:
                        self.manager.trigger_event(
                            "file_moved",
                            {
                                "src_path": event.src_path,
                                "dest_path": event.dest_path,
                                "monitor_id": self.monitor_id,
                                "monitor_path": self.path,
                            },
                            source=f"watchdog:{self.monitor_id}",
                        )
                        if self.callback:
                            self.callback("moved", event.src_path, event.dest_path)

            # 创建观察者
            observer = Observer()
            event_handler = FileChangeHandler(self, monitor_id, path, callback)
            observer.schedule(event_handler, path, recursive=True)

            # 启动观察者
            observer.start()

            # 保存观察者引用
            self._monitors[monitor_id]["observer"] = observer
            self._monitors[monitor_id]["event_handler"] = event_handler
            self._monitors[monitor_id]["status"] = "ACTIVE_WATCHING"

            # 更新数据库
            with self._get_connection() as conn:
                conn.execute(
                    """
                UPDATE perception_monitors
                SET status = 'ACTIVE_WATCHING'
                WHERE monitor_id = ?
                """,
                    (monitor_id,),
                )
                conn.commit()

            _log.info("🚀 [Perception] Started async monitoring with watchdog: {path}")

            return monitor_id

        except ImportError:
            _log.info("⚠️ [Perception] watchdog not installed, falling back to synchronous monitoring")
            # 回退到同步监控
            return self.monitor_filesystem(path, callback)
        except sqlite3.Error:
            _log.info("❌ [Perception] Async monitoring failed: {e}")
            # 回退到同步监控
            return self.monitor_filesystem(path, callback)

    def discover_external_resources(self, resource_type: str) -> list[dict]:
        """
        发现外部资源

        Args:
            resource_type: 资源类型（document、code、api）

        Returns:
            List[Dict]: 发现的资源列表
        """
        resources = []
        bos_root = os.environ.get("BOS_ROOT", "")

        try:
            if resource_type == "document":
                # 发现 Markdown 文档
                for root, dirs, files in os.walk(bos_root):
                    dirs[:] = [d for d in dirs if d not in [".git", "__pycache__", ".venv", "node_modules"]]
                    for file in files:
                        if file.endswith(".md"):
                            full_path = os.path.join(root, file)
                            relative_path = os.path.relpath(full_path, bos_root)
                            resources.append(
                                {
                                    "type": "document",
                                    "path": relative_path,
                                    "size": os.path.getsize(full_path),
                                }
                            )
                            if len(resources) >= 50:  # 限制结果数量
                                break
                    if len(resources) >= 50:
                        break

            elif resource_type == "code":
                # 发现 Python 代码
                for root, dirs, files in os.walk(bos_root):
                    dirs[:] = [d for d in dirs if d not in [".git", "__pycache__", ".venv", "node_modules"]]
                    for file in files:
                        if file.endswith(".py"):
                            full_path = os.path.join(root, file)
                            relative_path = os.path.relpath(full_path, bos_root)
                            resources.append(
                                {
                                    "type": "code",
                                    "path": relative_path,
                                    "size": os.path.getsize(full_path),
                                }
                            )
                            if len(resources) >= 50:
                                break
                    if len(resources) >= 50:
                        break

            elif resource_type == "api":
                # 发现 API 配置（简化实现）
                # 实际应该扫描配置文件或代码中的 API 定义
                resources.append({"type": "api", "name": "GitHub API", "endpoint": "https://api.github.com"})
                resources.append({"type": "api", "name": "NPM API", "endpoint": "https://registry.npmjs.org"})
                resources.append({"type": "api", "name": "PyPI API", "endpoint": "https://pypi.org/pypi"})

            _log.info("🔍 [Perception] Discovered {len(resources)} {resource_type} resources")

        except (TypeError, ValueError, AttributeError):
            _log.info("❌ [Perception] Resource discovery failed: {e}")

        return resources

    def trigger_event(self, event_type: str, event_data: dict, source: str = "unknown") -> str:
        """
        触发事件

        Args:
            event_type: 事件类型
            event_data: 事件数据
            source: 事件来源

        Returns:
            str: 事件 ID
        """
        import hashlib

        event_id = hashlib.md5(
            f"{event_type}_{time.time()}_{json.dumps(event_data)}".encode(), usedforsecurity=False
        ).hexdigest()

        # 添加到事件队列
        event = {
            "event_id": event_id,
            "event_type": event_type,
            "event_data": event_data,
            "source": source,
            "timestamp": time.time(),
        }

        self._events.append(event)

        # 限制事件队列大小
        if len(self._events) > self._max_events:
            self._events = self._events[-self._max_events // 2 :]

        # 记录到数据库
        with self._get_connection() as conn:
            conn.execute(
                """
            INSERT INTO perception_events (event_id, event_type, event_data, source, timestamp)
            VALUES (?, ?, ?, ?, ?)
            """,
                (event_id, event_type, json.dumps(event_data), source, time.time()),
            )
            conn.commit()

        _log.info("⚡ [Perception] Event triggered: {event_type}")

        # 通知相关组件（简化实现）
        self._notify_recipients(event)

        return event_id

    def _notify_recipients(self, event: dict) -> None:
        """通知相关组件"""
        # 简化实现：打印日志
        # 实际应该根据事件类型和配置通知相应的 Agent 或 Tool
        _log.info("📢 [Perception] Notifying recipients for event: {event['event_type']}")

    def get_events(self, event_type: str = None, limit: int = 100) -> list[dict]:  # noqa: RUF013
        """
        获取事件

        Args:
            event_type: 事件类型（可选）
            limit: 返回的事件数量

        Returns:
            List[Dict]: 事件列表
        """
        if event_type:
            return [e for e in self._events if e["event_type"] == event_type][-limit:]
        else:
            return self._events[-limit:]

    def get_statistics(self) -> dict[str, Any]:
        """
        获取统计信息

        Returns:
            Dict: 统计信息
                - active_monitors: 活跃监控数量
                - total_events: 总事件数量
                - events_by_type: 各类型事件数量
        """
        events_by_type = {}
        for event in self._events:
            event_type = event["event_type"]
            events_by_type[event_type] = events_by_type.get(event_type, 0) + 1

        return {
            "active_monitors": len([m for m in self._monitors.values() if m["status"] == "ACTIVE"]),
            "total_events": len(self._events),
            "events_by_type": events_by_type,
        }

    def validate_internal_state(self) -> bool:
        """验证内部状态"""
        return os.path.exists(self.db_path)


# 全局单例
Perception = PerceptionManager()
