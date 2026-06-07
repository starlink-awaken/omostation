from __future__ import annotations

# ruff: noqa: RUF001, RUF002, RUF003
import asyncio

from ._compat import ProjectPaths

"""
---
Type: Module
Status: ACTIVE
Layer: L3
Authority: nucleus/Z-Core/L0-Genome/R0-ACT-SYS-AX01-10_holographic_metadata_axiom.md
---
"""


import logging
import os
import sqlite3
import threading
import time
from contextlib import closing

# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Microkernel_Component ≡ Distributed_Janitor
# 内涵 ≝ {Cleanup, Coordinate, Elect}
# 外延 ≝ {j | j ∈ Z-Microkernel ∧ manages(j, MessageLifecycle)}
# 功能 ⊢ {LeaderElection, DistributedCleanup, TTLCoordination,DeadLetterRemoval}
# =============================================================================

"""
---
Type: Daemon
Status: ACTIVE
Version: 1.0.0
Owner: '@SecurityLead'
Layer: Z-Microkernel
Summary: 'Distributed Message Janitor with Leader Election - Prevents duplicate cleanup in multi-process deployments'
Tags:
- janitor
- distributed
- leader-election
- cleanup
- coordination
Authority: organs/D-Execution/AGENTS.md
---
"""

# Configure logging
_log = logging.getLogger(__name__)


logger = logging.getLogger(__name__)

DB_PATH = os.environ.get("BOS_ROUTER_DB", str(ProjectPaths.get_core_db_path("messages.db")))


class DistributedMessageJanitor:
    """
    分布式消息看门人 - 带Leader选举的TTL执行和死信清理

    特性:
    1. Leader选举 - 只有一个实例执行清理，避免竞争
    2. 自动故障转移 - Leader失效后自动选举新Leader
    3. 协调清理 - 防止多实例重复清理相同消息
    4. 统计报告 - 清理结果的可观测性
    """

    LEADER_LOCK_ID = 42  # 固定ID用于advisory lock
    LEADER_HEARTBEAT_INTERVAL = 30  # Leader心跳间隔（秒）
    LEADER_TIMEOUT = 60  # Leader失效超时（秒）

    def __init__(self, interval_seconds: int = 60, leader_lease_seconds: int = 60) -> None:
        self.status = "active"  # was super().__init__(metadata_path=...)
        """
        初始化分布式看门人

        Args:
            interval_seconds: 清理间隔（秒）
            leader_lease_seconds: Leader租约时长（秒）
        """
        self.interval = interval_seconds
        self.leader_lease = leader_lease_seconds
        self.running = False
        self._thread: threading.Thread | None = None
        self._instance_id = f"{os.getpid()}_{threading.current_thread().ident}"
        self._is_leader = False
        self._leader_heartbeat_time = 0.0

        # 统计信息
        self.stats = {
            "cleanup_runs": 0,
            "ttl_cleaned": 0,
            "dead_cleaned": 0,
            "errors": 0,
            "leadership_acquired": 0,
            "leadership_lost": 0,
        }

        logger.info(f"DistributedMessageJanitor initialized (instance: {self._instance_id})")

    def _ensure_coordination_table(self) -> None:
        """确保协调表存在（用于Leader选举）"""
        try:
            with closing(sqlite3.connect(DB_PATH, timeout=10)) as conn:
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS janitor_coordination (
                        lock_id INTEGER PRIMARY KEY,
                        leader_instance TEXT,
                        leader_heartbeat REAL,
                        cleanup_count INTEGER DEFAULT 0,
                        created_at REAL DEFAULT (strftime('%s', 'now'))
                    )
                """
                )
                # 初始化锁记录
                conn.execute(
                    """
                    INSERT OR IGNORE INTO janitor_coordination (lock_id, leader_instance, leader_heartbeat)
                    VALUES (?, '', 0)
                    """,
                    (self.LEADER_LOCK_ID,),
                )
                conn.commit()
        except sqlite3.Error as e:
            logger.error(f"Error ensuring coordination table: {e}")

    def _try_acquire_leadership(self) -> bool:
        """
        尝试获取Leader身份

        Returns:
            True if successfully became leader
        """
        try:
            with closing(sqlite3.connect(DB_PATH, timeout=5)) as conn:
                conn.execute("PRAGMA journal_mode=WAL")
                now = time.time()

                # 尝试成为Leader的条件:
                # 1. 当前无Leader (leader_instance = '')
                # 2. 当前Leader已超时 (leader_heartbeat < now - LEADER_TIMEOUT)
                cursor = conn.execute(
                    """
                    UPDATE janitor_coordination
                    SET leader_instance = ?, leader_heartbeat = ?
                    WHERE lock_id = ?
                    AND (
                        leader_instance = ''
                        OR leader_heartbeat < ?
                        OR leader_instance = ?
                    )
                    """,
                    (
                        self._instance_id,
                        now,
                        self.LEADER_LOCK_ID,
                        now - self.LEADER_TIMEOUT,
                        self._instance_id,  # 允许续租
                    ),
                )
                conn.commit()

                if cursor.rowcount > 0:
                    # 确认自己是Leader
                    leader = conn.execute(
                        "SELECT leader_instance FROM janitor_coordination WHERE lock_id = ?",
                        (self.LEADER_LOCK_ID,),
                    ).fetchone()

                    if leader and leader[0] == self._instance_id:
                        if not self._is_leader:
                            self._is_leader = True
                            self.stats["leadership_acquired"] += 1
                            logger.info(f"🎖️ [{self._instance_id}] Became Leader")
                        self._leader_heartbeat_time = now
                        return True

                # 不是Leader
                if self._is_leader:
                    self._is_leader = False
                    self.stats["leadership_lost"] += 1
                    logger.info(f"👋 [{self._instance_id}] Lost Leadership")

                return False

        except sqlite3.OperationalError as e:
            logger.warning(f"Database lock during leadership acquisition: {e}")
            return False
        except sqlite3.Error as e:
            logger.error(f"Error acquiring leadership: {e}")
            return False

    def _renew_leadership(self) -> bool:
        """续租Leader身份"""
        if not self._is_leader:
            return False

        try:
            with closing(sqlite3.connect(DB_PATH, timeout=5)) as conn:
                now = time.time()
                cursor = conn.execute(
                    """
                    UPDATE janitor_coordination
                    SET leader_heartbeat = ?
                    WHERE lock_id = ? AND leader_instance = ?
                    """,
                    (now, self.LEADER_LOCK_ID, self._instance_id),
                )
                conn.commit()

                if cursor.rowcount > 0:
                    self._leader_heartbeat_time = now
                    return True
                else:
                    # 续租失败，失去Leader身份
                    self._is_leader = False
                    self.stats["leadership_lost"] += 1
                    logger.warning(f"👋 [{self._instance_id}] Leadership renewal failed")
                    return False

        except sqlite3.Error as e:
            logger.error(f"Error renewing leadership: {e}")
            return False

    def _release_leadership(self) -> None:
        """主动释放Leader身份"""
        if not self._is_leader:
            return

        try:
            with closing(sqlite3.connect(DB_PATH, timeout=5)) as conn:
                conn.execute(
                    """
                    UPDATE janitor_coordination
                    SET leader_instance = '', leader_heartbeat = 0
                    WHERE lock_id = ? AND leader_instance = ?
                    """,
                    (self.LEADER_LOCK_ID, self._instance_id),
                )
                conn.commit()

                self._is_leader = False
                logger.info(f"🚪 [{self._instance_id}] Released Leadership")
        except sqlite3.Error as e:
            logger.error(f"Error releasing leadership: {e}")

    def start(self) -> None:
        if self.running:
            return

        self._ensure_coordination_table()
        self.running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info(f"🧹 [DistributedMessageJanitor] Started (instance: {self._instance_id})")

    def stop(self) -> None:
        self.running = False
        self._release_leadership()
        if self._thread:
            self._thread.join(timeout=2)
        logger.info("🧹 [DistributedMessageJanitor] Stopped")

    def _run_loop(self) -> None:
        last_cleanup = 0
        last_heartbeat = 0

        while self.running:
            now = time.time()

            try:
                # 1. 尝试获取或续租Leader身份
                if not self._is_leader:
                    self._try_acquire_leadership()
                elif now - last_heartbeat > self.LEADER_HEARTBEAT_INTERVAL:
                    if not self._renew_leadership():
                        # 续租失败，尝试重新获取
                        self._try_acquire_leadership()
                    last_heartbeat = now

                # 2. 只有Leader执行清理
                if self._is_leader and now - last_cleanup > self.interval:
                    self._do_cleanup()
                    last_cleanup = now

                # 3. 非Leader定期检查是否有Leader
                elif not self._is_leader and now - last_heartbeat > self.LEADER_TIMEOUT:
                    # 长时间没有Leader，尝试获取
                    self._try_acquire_leadership()
                    last_heartbeat = now

            except (TimeoutError, asyncio.CancelledError) as e:
                logger.error(f"Error in janitor loop: {e}")
                self.stats["errors"] += 1

            time.sleep(1)  # 每秒检查一次

    def _do_cleanup(self) -> None:
        now = time.time()
        ttl_deleted = 0
        dead_deleted = 0

        try:
            with sqlite3.connect(DB_PATH, timeout=10) as conn:
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("PRAGMA synchronous=NORMAL")
                cursor = conn.cursor()

                # 1. TTL Enforcement
                cursor.execute(
                    """
                    DELETE FROM messages
                    WHERE ttl > 0
                    AND (created_at + ttl) < ?
                    AND status IN ('pending', 'read')
                    """,
                    (now,),
                )
                ttl_deleted = cursor.rowcount

                # 2. Dead Letter Cleanup (24小时)
                twenty_four_hours_ago = now - (24 * 3600)
                cursor.execute(
                    """
                    DELETE FROM messages
                    WHERE created_at < ?
                    AND status IN ('processed', 'failed', 'cancelled')
                    """,
                    (twenty_four_hours_ago,),
                )
                dead_deleted = cursor.rowcount

                # 3. 更新清理计数
                conn.execute(
                    """
                    UPDATE janitor_coordination
                    SET cleanup_count = cleanup_count + ?
                    WHERE lock_id = ?
                    """,
                    (ttl_deleted + dead_deleted, self.LEADER_LOCK_ID),
                )

                conn.commit()

                self.stats["cleanup_runs"] += 1
                self.stats["ttl_cleaned"] += ttl_deleted
                self.stats["dead_cleaned"] += dead_deleted

                if ttl_deleted > 0 or dead_deleted > 0:
                    logger.info(f"🧹 [Leader {self._instance_id}] Cleaned: {ttl_deleted} TTL, {dead_deleted} Dead")

        except sqlite3.OperationalError as e:
            logger.warning(f"Database locked during cleanup: {e}")
        except sqlite3.Error as e:
            logger.error(f"Error during cleanup: {e}")
            self.stats["errors"] += 1

    def get_status(self) -> dict:
        """
        获取看门人状态

        Returns:
            状态信息字典
        """
        return {
            "instance_id": self._instance_id,
            "is_leader": self._is_leader,
            "running": self.running,
            "stats": self.stats.copy(),
            "last_heartbeat": self._leader_heartbeat_time,
            "leader_lease_seconds": self.leader_lease,
        }


# 便捷函数：创建并启动看门人
def start_message_janitor(interval_seconds: int = 60) -> DistributedMessageJanitor:
    """
    启动消息看门人

    Args:
        interval_seconds: 清理间隔（秒）

    Returns:
        看门人实例
    """
    janitor = DistributedMessageJanitor(interval_seconds=interval_seconds)
    janitor.start()
    return janitor
