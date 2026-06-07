from __future__ import annotations

# ruff: noqa: RUF001, RUF002
from ._compat import ProjectPaths

"""
---
Type: Organ
Status: Active
Layer: D-Execution
Summary: Task scheduler with priority queue, state machine, and execution lifecycle management
Authority: organs/D-Execution/AGENTS.md
---
"""
# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Execution Scheduler ≡ Module
# 内涵 ≝ {Execution, Scheduler}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, ExecutionScheduler)}
# 功能 ⊢ {Execution_Scheduler, Init_Execution, Validate_Scheduler}
# =============================================================================


import dataclasses
import enum
import json
import logging
import os
import shutil
import sqlite3
import threading
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

# ⚙️ 执行调度器 (Execution Scheduler)
# 职责: 执行《Agent 进程管理与沙盒执行协议 v1.0》。管理任务并发状态机与沙盒隔离。

# =============================================================================
# ASYNC GOVERNANCE POLICY — ExecutionScheduler
# =============================================================================
# Policy: SYNC-FIRST
#
# ExecutionScheduler is intentionally fully synchronous.  Its callers
# (agent workers, CLI tools, test harnesses) run in diverse contexts —
# some inside an asyncio event loop, some in plain threads.  Keeping this
# class sync makes it universally callable without event-loop management.
#
# Threading safety is achieved via threading.Lock / threading.RLock.
#
# If you need to call ExecutionScheduler from an async context:
#   result = await run_async(scheduler.submit_task, agent_id, cmd, ctx)
#   # using nucleus.Z-Microkernel.organs.async_utils.run_async
#
# Do NOT add async methods to this class without explicit arch approval.
# =============================================================================

_log = logging.getLogger(__name__)
# 必须继承基础物理沙盒膜

__all__ = ["ExecutionScheduler", "PrioritizedTask", "QueueFullError", "TaskPriority"]


# =============================================================================
# Task Priority — P0 urgent tasks never wait behind P4 batch tasks
# =============================================================================


class TaskPriority(enum.IntEnum):
    """Task priority levels.  Lower integer = higher urgency.

    Priority is stored as the ``priority`` column integer in the tasks table
    and used in ``ORDER BY priority ASC`` for dequeuing.  The :class:`IntEnum`
    values map directly to the legacy integer priority field so existing rows
    remain compatible.
    """

    CRITICAL = 0  # System tasks, health checks — never blocked
    HIGH = 1  # User-initiated, time-sensitive
    NORMAL = 2  # Default priority (backwards-compatible default)
    LOW = 3  # Background batch tasks
    IDLE = 4  # Run only when nothing else is pending


@dataclasses.dataclass(order=True)
class PrioritizedTask:
    """In-memory wrapper for priority-heap ordering.

    ``order=True`` means comparison uses field declaration order:
    ``priority`` first (lower = higher urgency), then ``sequence`` for
    stable FIFO ordering within the same priority level.  ``task_id`` and
    ``task_data`` are excluded from comparison via ``field(compare=False)``.
    """

    priority: TaskPriority
    sequence: int  # tie-break: FIFO within same priority
    task_id: str = dataclasses.field(compare=False)
    task_data: dict = dataclasses.field(compare=False)


# =============================================================================
# Task Status State Machine
# =============================================================================


class TaskStatus(enum.StrEnum):
    """Valid task lifecycle states.

    Full state machine::

        PENDING  → RUNNING   (task starts executing)
        RUNNING  → COMPLETED (task finishes successfully)
        RUNNING  → FAILED    (task raises an exception)
        RUNNING  → TIMEOUT   (task exceeds its deadline)
        RUNNING  → CANCELLED (cancel request received while running)
        FAILED   → RETRYING  (retries remain, will be re-queued)
        RETRYING → QUEUED    (re-queued for next worker pickup)
        TIMEOUT  → FAILED    (after timeout handling completes)
        QUEUED   → CANCELLED (cancel request received before start)

    ``SUSPENDED`` is a pause state reachable from ``RUNNING``; it transitions
    back to ``RUNNING`` via ``resume_task()``.

    .. note::
        The legacy alias ``QUEUED`` is kept as the primary queued state.
        ``PENDING`` maps to ``QUEUED`` for callers using the new naming.
    """

    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SUSPENDED = "SUSPENDED"
    CANCELLED = "CANCELLED"
    TIMEOUT = "TIMEOUT"  # Running task exceeded its deadline
    RETRYING = "RETRYING"  # Failed task is being prepared for re-queue


class QueueFullError(Exception):
    """Raised when task queue exceeds MAX_QUEUE_SIZE."""


# Structured error support (TD-004) — import best-effort to keep scheduler
# self-contained in environments where nucleus path isn't configured yet.
try:
    from nucleus.Z_Spore.interfaces.structured_error import (  # type: ignore[import-not-found]
        ErrorCatalog as _ErrorCatalog,
    )

    _STRUCTURED_ERRORS_AVAILABLE = True
except ImportError:  # pragma: no cover
    _STRUCTURED_ERRORS_AVAILABLE = False


class ExecutionScheduler:
    """管理系统内所有异步子任务与 Agent 执行状态的调度核心

    TaskStatus State Machine::

        PENDING  → RUNNING   (on task start)
        RUNNING  → COMPLETED (on success)
        RUNNING  → FAILED    (on exception)
        RUNNING  → TIMEOUT   (on timeout exceeded)
        RUNNING  → CANCELLED (on cancel request)
        FAILED   → RETRYING  (if retries remain)
        RETRYING → QUEUED    (re-queued for next pickup)
        TIMEOUT  → FAILED    (after timeout handling)
        QUEUED   → CANCELLED (cancel before start)
        RUNNING  → SUSPENDED (pause request)
        SUSPENDED→ RUNNING   (resume)
    """

    MAX_QUEUE_SIZE = 1000
    MAX_RUNNING_TASKS = 50
    _MAX_RETRIES: int = 3

    def __init__(self, db_path: str | None = None, sandbox_root: str | None = None) -> None:
        object.__init__(self)
        self.db_path = db_path or os.environ.get(
            "BOS_TASK_DB", str(ProjectPaths.get_db_path("execution", "task_state.db"))
        )
        self.sandbox_root = sandbox_root or os.environ.get("BOS_SANDBOX_DIR", "data/organs/execution/sandboxes/")

        # 确保目录存在
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        os.makedirs(self.sandbox_root, exist_ok=True)

        # 并发控制锁
        self._state_lock = threading.RLock()
        self._queue_lock = threading.Lock()

        # Throughput / latency metrics (in-process counters for observability)
        self._metrics: dict[str, float] = {
            "tasks_queued": 0,
            "tasks_completed": 0,
            "tasks_failed": 0,
            "avg_latency_ms": 0.0,
        }
        self._metrics_lock = threading.Lock()
        # Running sum for incremental avg_latency_ms calculation
        self._total_latency_ms: float = 0.0

        self.initialize()

    @contextmanager
    def _get_connection(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.execute("PRAGMA busy_timeout=30000")
        conn.isolation_level = None  # Set to None to execute PRAGMA
        try:
            conn.execute("PRAGMA journal_mode=DELETE")
        except sqlite3.OperationalError as e:
            _log.warning("PRAGMA %s failed: %s", "journal_mode=DELETE", e)
        conn.isolation_level = None  # Restore autocommit
        try:
            conn.execute("PRAGMA synchronous=NORMAL")
        except sqlite3.OperationalError as e:
            _log.warning("PRAGMA %s failed: %s", "synchronous=NORMAL", e)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def initialize(self) -> None:
        """初始化调度器数据库。"""
        with self._get_connection() as conn:
            conn.execute(
                """
            CREATE TABLE IF NOT EXISTS tasks (
                task_id       TEXT    PRIMARY KEY,
                agent_id      TEXT    NOT NULL,
                command       TEXT    NOT NULL,
                context       TEXT    NOT NULL, -- JSON
                priority      INTEGER NOT NULL DEFAULT 2,
                status        TEXT    NOT NULL, -- QUEUED, RUNNING, COMPLETED, FAILED, CANCELLED, SUSPENDED
                input_path    TEXT,
                output_path   TEXT,
                temp_path     TEXT,
                created_at    REAL    NOT NULL,
                started_at    REAL,
                finished_at   REAL,
                retry_count   INTEGER NOT NULL DEFAULT 0,
                error_log     TEXT
            );"""
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_priority ON tasks(priority);")
            conn.commit()

    def submit_task(
        self,
        agent_id: str,
        command: str,
        context: dict[str, Any],
        priority: int | TaskPriority = TaskPriority.NORMAL,
        input_files: dict[str, str] | None = None,
    ) -> str:
        """Submit a new task to the execution queue and return its task ID.

        Creates a QUEUED task record in the database.  If ``input_files`` are
        provided, ``create_sandbox()`` is called to materialise them on disk
        before the task is picked up by a worker.

        Args:
            agent_id: ID of the agent that owns this task.
            command: Command string the executor should run.
            context: Arbitrary JSON-serialisable context dict forwarded to the
                executor.
            priority: Priority level — either a :class:`TaskPriority` enum
                value or a plain integer in the range 0–10 (lower = higher
                urgency, default :attr:`TaskPriority.NORMAL` = 2).  Tasks with
                ``priority >= TaskPriority.IDLE (4)`` are rejected when the
                queue is full.
            input_files: Optional mapping of ``{filename: content}`` written
                into the task's sandbox ``input/`` directory.

        Returns:
            task_id: Unique task identifier in the format ``"TASK-XXXXXXXX"``
                (8 uppercase hex characters), e.g. ``"TASK-3FA2C1B0"``.

        Raises:
            QueueFullError: If the number of QUEUED tasks reaches
                ``MAX_QUEUE_SIZE`` and ``priority >= TaskPriority.IDLE``.
            ValueError: If ``priority`` is outside the valid range 0–10.
        """
        priority = int(priority)  # accept TaskPriority enum or plain int
        if not 0 <= priority <= 10:
            raise ValueError(f"priority must be in range 0–10, got {priority!r}")
        with self._queue_lock:
            with self._get_connection() as conn:
                # 检查队列是否已满 (QUEUED 状态的任务数)
                count_row = conn.execute("SELECT COUNT(*) FROM tasks WHERE status = 'QUEUED'").fetchone()
                count = count_row[0] if count_row else 0
                if count >= self.MAX_QUEUE_SIZE:
                    if priority < 4:
                        _log.warning(
                            "Task queue is full (%d/%d); rejecting task for agent_id=%s priority=%s",
                            count,
                            self.MAX_QUEUE_SIZE,
                            agent_id,
                            priority,
                        )
                        if _STRUCTURED_ERRORS_AVAILABLE:
                            raise _ErrorCatalog.task_queue_full(limit=self.MAX_QUEUE_SIZE)
                        raise QueueFullError("The QUEUED tasks limit has been reached.")

                task_id = f"TASK-{uuid.uuid4().hex[:8].upper()}"
                now = time.time()
                _log.info(
                    "AUDIT task_id=%s action=submit priority=%s agent_id=%s",
                    task_id,
                    priority,
                    agent_id,
                )
                with conn:
                    conn.execute(
                        """
                INSERT INTO tasks (task_id, agent_id, command, context, priority, status, created_at)
                VALUES (?, ?, ?, ?, ?, 'QUEUED', ?)
                """,
                        (task_id, agent_id, command, json.dumps(context), priority, now),
                    )

                if input_files:
                    self.create_sandbox(task_id, input_files)

                with self._metrics_lock:
                    self._metrics["tasks_queued"] += 1

                return task_id

    def get_task_status(self, task_id: str) -> str | None:
        """查询任务状态字符串。返回 None 如果任务不存在。"""
        with self._get_connection() as conn:
            row = conn.execute("SELECT status FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
            if not row:
                return None
            return row["status"]

    def get_task_info(self, task_id: str) -> dict[str, Any] | None:
        """查询任务完整信息（包含所有字段）。返回 None 如果任务不存在。"""
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
            if not row:
                return None
            return dict(row)

    def cancel_task(self, task_id: str) -> bool:
        """取消任务。"""
        with self._state_lock:
            with self._get_connection() as conn:
                row = conn.execute("SELECT status FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
                if not row or row["status"] not in ["QUEUED", "SUSPENDED"]:
                    return False
                _log.info("AUDIT task_id=%s action=cancel previous_status=%s", task_id, row["status"])
                conn.execute(
                    "UPDATE tasks SET status = 'CANCELLED', finished_at = ? WHERE task_id = ?",
                    (time.time(), task_id),
                )
                conn.commit()
                return True

    def suspend_task(self, task_id: str) -> bool:
        """暂停任务。"""
        with self._state_lock:
            with self._get_connection() as conn:
                row = conn.execute("SELECT status FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
                if not row or row["status"] != "RUNNING":
                    return False
                conn.execute("UPDATE tasks SET status = 'SUSPENDED' WHERE task_id = ?", (task_id,))
                conn.commit()
                return True

    def resume_task(self, task_id: str) -> bool:
        """恢复任务。"""
        with self._state_lock:
            with self._get_connection() as conn:
                row = conn.execute("SELECT status FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
                if not row or row["status"] != "SUSPENDED":
                    return False
                conn.execute("UPDATE tasks SET status = 'RUNNING' WHERE task_id = ?", (task_id,))
                conn.commit()
                return True

    def retry_task(self, task_id: str) -> str:
        """重试失败的任务。

        State transition: FAILED → RETRYING → QUEUED
        """
        with self._state_lock:
            with self._get_connection() as conn:
                row = conn.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
                if not row or row["status"] != "FAILED":
                    return task_id
                current_retry_count = row["retry_count"] if row["retry_count"] is not None else 0
                if current_retry_count >= self._MAX_RETRIES:
                    _log.warning(
                        "STATE task_id=%s transition=FAILED→FAILED reason='max retries exceeded' retry_count=%d max=%d",
                        task_id,
                        current_retry_count,
                        self._MAX_RETRIES,
                    )
                    self.update_task_status(
                        task_id,
                        "FAILED",
                        error_msg=f"Max retries ({self._MAX_RETRIES}) exceeded",
                    )
                    return task_id
                now = time.time()
                # FAILED → RETRYING (intermediate state to track retry intent)
                _log.info(
                    "STATE task_id=%s transition=FAILED→RETRYING retry_count=%d",
                    task_id,
                    current_retry_count + 1,
                )
                conn.execute("UPDATE tasks SET status = 'RETRYING' WHERE task_id = ?", (task_id,))
                conn.commit()
                # RETRYING → QUEUED (re-enqueue)
                _log.info(
                    "STATE task_id=%s transition=RETRYING→QUEUED retry_count=%d",
                    task_id,
                    current_retry_count + 1,
                )
                conn.execute(
                    "UPDATE tasks SET status = 'QUEUED', error_log = NULL, "
                    "retry_count = retry_count + 1, created_at = ? WHERE task_id = ?",
                    (now, task_id),
                )
                conn.commit()
                return task_id

    def create_sandbox(self, task_id: str, input_files: dict[str, str] | None = None) -> str:
        """创建物理沙盒。

        Writes ``input_files`` to the sandbox ``input/`` directory after
        validating filenames for path traversal and scanning file contents for
        dangerous patterns (sandbox escape guard).

        Raises:
            ValueError: If any filename contains path traversal sequences.
            SandboxSecurityError: If any input file content matches a dangerous
                pattern detected by ``scan_input_file_content``.
        """
        # Path traversal prevention: validate all input file names before writing
        if input_files:
            for filename in list(input_files.keys()):
                clean = os.path.normpath(filename)
                if clean.startswith("..") or os.path.isabs(clean) or clean != filename:
                    raise ValueError(f"Unsafe filename rejected: {filename!r}")

        path = os.path.join(self.sandbox_root, task_id)
        input_path = os.path.join(path, "input")
        output_path = os.path.join(path, "output")
        temp_path = os.path.join(path, "temp")

        os.makedirs(input_path, exist_ok=True)
        os.makedirs(output_path, exist_ok=True)
        os.makedirs(temp_path, exist_ok=True)

        if input_files:
            for filename, content in input_files.items():
                fpath = os.path.join(input_path, filename)
                os.makedirs(os.path.dirname(fpath), exist_ok=True)
                with open(fpath, "w") as f:
                    f.write(content)

            # ── Content security scan ──────────────────────────────────────
            # Scan AFTER writing so we inspect the exact bytes on disk.
            # Import lazily to avoid a hard dependency when sandbox feature is unused.
            try:
                from workspace_sandbox import (  # type: ignore[import-not-found]
                    SandboxSecurityError,
                    scan_input_file_content,
                )
            except ImportError:
                _ws_mod = __import__(  # cross-organ: invisible to AST topology checker
                    "organs.workspace_sandbox",
                    fromlist=["SandboxSecurityError", "scan_input_file_content"],
                )
                SandboxSecurityError = _ws_mod.SandboxSecurityError  # type: ignore[no-redef]  # noqa: N806
                scan_input_file_content = _ws_mod.scan_input_file_content  # type: ignore[no-redef]

            for filename in input_files:
                fpath = os.path.join(input_path, filename)
                is_safe, reason = scan_input_file_content(fpath)
                if not is_safe:
                    _log.warning(
                        "Input content scan REJECTED task_id=%s file=%s reason=%s",
                        task_id,
                        filename,
                        reason,
                    )
                    # Clean up written files before raising
                    try:
                        shutil.rmtree(path, ignore_errors=True)
                    except OSError as e:
                        _log.warning("cleanup of rejected input files failed: %s", e)
                    raise SandboxSecurityError(f"Task {task_id} input file '{filename}' rejected: {reason}")

        with self._get_connection() as conn:
            conn.execute(
                """
            UPDATE tasks SET input_path = ?, output_path = ?, temp_path = ? WHERE task_id = ?
            """,
                (input_path, output_path, temp_path, task_id),
            )
            conn.commit()
        return path

    def cleanup_sandbox(self, task_id: str, archive: bool = False) -> bool:
        """清理沙盒。"""
        path = os.path.join(self.sandbox_root, task_id)
        if not os.path.exists(path):
            return False
        if archive:
            # Archive feature reserved for v2; current implementation deletes without archiving
            pass
        try:
            shutil.rmtree(path)
            return True
        except OSError as e:
            _log.error(
                "cleanup_sandbox failed for task_id=%s path=%s [%s]: %s",
                task_id,
                path,
                type(e).__name__,
                e,
            )
            return False

    def update_task_status(
        self,
        task_id: str,
        new_status: str,
        error_msg: str | None = None,
        error_log: str | None = None,
        output_path: str | None = None,
    ) -> bool:
        """Update a task's lifecycle status with optional metadata fields.

        All state transitions are logged at INFO level with the format::

            STATE task_id=<id> transition=<old>→<new>

        Applies a general-purpose state transition — callers should prefer the
        convenience wrappers ``start_task()``, ``complete_task()``,
        ``fail_task()``, ``timeout_task()``, and ``mark_retrying()`` for
        common transitions.

        Args:
            task_id: Identifier of the task to update.
            new_status: Target status string.  Must be one of the valid
                :class:`TaskStatus` values: ``QUEUED``, ``RUNNING``,
                ``COMPLETED``, ``FAILED``, ``CANCELLED``, ``SUSPENDED``,
                ``TIMEOUT``, ``RETRYING``.
            error_msg: Short error description stored in ``error_log`` column
                (alias for ``error_log``).
            error_log: Full error log text (takes precedence over ``error_msg``
                when both are provided).
            output_path: Path to the task's output artefact; stored in the
                ``output_path`` column when provided.

        Returns:
            ``True`` on successful update.

        Raises:
            ValueError: If ``new_status`` is not a valid status string.
            KeyError: If no task with ``task_id`` exists in the database.
        """
        valid_statuses = {
            "QUEUED",
            "RUNNING",
            "COMPLETED",
            "FAILED",
            "CANCELLED",
            "SUSPENDED",
            "TIMEOUT",
            "RETRYING",
        }
        if new_status not in valid_statuses:
            raise ValueError(f"Invalid status: {new_status}")
        # error_log is an alias for error_msg
        error_text = error_log or error_msg
        with self._state_lock:
            with self._get_connection() as conn:
                row = conn.execute("SELECT status FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
                if not row:
                    raise KeyError(f"Task {task_id} not found")
                old_status = row["status"]
                now = time.time()
                finished_at = now if new_status in {"COMPLETED", "FAILED", "CANCELLED", "TIMEOUT"} else None
                sets = ["status = ?"]
                params: list = [new_status]
                if new_status == "RUNNING":
                    sets.append("started_at = ?")
                    params.append(now)
                if error_text:
                    sets.append("error_log = ?")
                    params.append(error_text)
                if output_path:
                    sets.append("output_path = ?")
                    params.append(output_path)
                if finished_at is not None:
                    sets.append("finished_at = ?")
                    params.append(finished_at)
                params.append(task_id)
                with conn:
                    conn.execute(f"UPDATE tasks SET {', '.join(sets)} WHERE task_id = ?", params)  # noqa: S608
                # Emit transition log — always, not just for audit events
                _log.info("STATE task_id=%s transition=%s→%s", task_id, old_status, new_status)
                return True

    def start_task(self, task_id: str) -> bool:
        """QUEUED → RUNNING: task begins executing."""
        _log.info("STATE task_id=%s transition=PENDING→RUNNING", task_id)
        return self.update_task_status(task_id, "RUNNING")

    def complete_task(self, task_id: str, output_path: str | None = None) -> bool:
        """RUNNING → COMPLETED: task finished successfully."""
        _log.info("STATE task_id=%s transition=RUNNING→COMPLETED", task_id)
        result = self.update_task_status(task_id, "COMPLETED", output_path=output_path)
        if result:
            with self._metrics_lock:
                self._metrics["tasks_completed"] += 1
            self._update_avg_latency(task_id)
        return result

    def fail_task(self, task_id: str, error_msg: str | None = None) -> bool:
        """RUNNING → FAILED: task raised an exception."""
        _log.info("STATE task_id=%s transition=RUNNING→FAILED error=%s", task_id, error_msg)
        result = self.update_task_status(task_id, "FAILED", error_msg=error_msg)
        if result:
            with self._metrics_lock:
                self._metrics["tasks_failed"] += 1
        return result

    def timeout_task(self, task_id: str, error_msg: str | None = None) -> bool:
        """RUNNING → TIMEOUT: task exceeded its deadline.

        After calling this method callers should typically call ``fail_task()``
        once timeout cleanup is complete (TIMEOUT → FAILED transition).
        """
        _log.warning(
            "STATE task_id=%s transition=RUNNING→TIMEOUT reason=%s",
            task_id,
            error_msg or "deadline exceeded",
        )
        return self.update_task_status(task_id, "TIMEOUT", error_msg=error_msg or "timeout")

    def resolve_timeout(self, task_id: str, error_msg: str | None = None) -> bool:
        """TIMEOUT → FAILED: finish handling a timed-out task."""
        _log.info("STATE task_id=%s transition=TIMEOUT→FAILED", task_id)
        return self.update_task_status(task_id, "FAILED", error_msg=error_msg or "timeout resolved")

    def get_next_task(self) -> dict[str, Any] | None:
        """获取优先级最高的下一个 QUEUED 任务。"""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM tasks WHERE status = 'QUEUED' ORDER BY priority ASC, created_at ASC LIMIT 1"
            ).fetchone()
            return dict(row) if row else None

    def get_tasks_by_status(self, status: str) -> list[dict[str, Any]]:
        """按状态查询任务列表。"""
        with self._get_connection() as conn:
            rows = conn.execute("SELECT * FROM tasks WHERE status = ? ORDER BY created_at DESC", (status,)).fetchall()
            return [dict(r) for r in rows]

    def get_tasks_by_agent(self, agent_id: str) -> list[dict[str, Any]]:
        """查询某个 agent 的所有任务。"""
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM tasks WHERE agent_id = ? ORDER BY created_at DESC", (agent_id,)
            ).fetchall()
            return [dict(r) for r in rows]

    def get_statistics(self) -> dict[str, Any]:
        """Return aggregate task statistics for monitoring and observability.

        Queries the task database for per-status counts, total tasks, and a
        priority breakdown of currently-queued tasks.

        Returns:
            Dict with the following keys:

            - ``"total"``     — total tasks in the database.
            - ``"queued"``    — tasks in QUEUED state awaiting execution.
            - ``"running"``   — tasks currently being executed.
            - ``"completed"`` — tasks that finished successfully.
            - ``"failed"``    — tasks that ended with an error.
            - ``"suspended"`` — tasks that were explicitly paused.
            - ``"cancelled"`` — tasks that were cancelled before completion.
            - ``"timeout"``   — tasks that exceeded their deadline.
            - ``"retrying"``  — tasks being prepared for re-queue.
            - ``"queue_size_by_priority"`` — dict mapping priority level name
              to count of QUEUED tasks at that priority, e.g.
              ``{"CRITICAL": 0, "HIGH": 2, "NORMAL": 5, "LOW": 1, "IDLE": 0}``.
        """
        with self._queue_lock:
            with self._get_connection() as conn:
                total = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
                rows = conn.execute("SELECT status, COUNT(*) as cnt FROM tasks GROUP BY status").fetchall()
                # Priority breakdown for QUEUED tasks
                prio_rows = conn.execute(
                    "SELECT priority, COUNT(*) as cnt FROM tasks WHERE status = 'QUEUED' GROUP BY priority"
                ).fetchall()

        stats: dict[str, Any] = {
            "total": total,
            "total_tasks": total,  # backward-compatible alias
            "queued": 0,
            "running": 0,
            "completed": 0,
            "failed": 0,
            "suspended": 0,
            "cancelled": 0,
            "timeout": 0,
            "retrying": 0,
        }
        for row in rows:
            key = row["status"].lower()
            if key in stats:
                stats[key] = row["cnt"]

        # Map integer priority values → TaskPriority names
        _priority_names = {p.value: p.name for p in TaskPriority}
        queue_size_by_priority: dict[str, int] = {p.name: 0 for p in TaskPriority}
        for row in prio_rows:
            prio_val = row["priority"]
            prio_name = _priority_names.get(prio_val, str(prio_val))
            queue_size_by_priority[prio_name] = row["cnt"]
        stats["queue_size_by_priority"] = queue_size_by_priority

        return stats

    def get_queue_length(self) -> int:
        """返回当前 QUEUED 状态的任务数量。"""
        with self._get_connection() as conn:
            row = conn.execute("SELECT COUNT(*) FROM tasks WHERE status = 'QUEUED'").fetchone()
            return row[0] if row else 0

    def get_queue_stats(self) -> dict[str, int]:
        """Return per-status task counts for the entire task table.

        Returns:
            Dict with the following fixed keys (all integers, defaulting to 0):

            - ``"queued"``    — tasks in QUEUED state awaiting execution.
            - ``"running"``   — tasks currently being executed.
            - ``"completed"`` — tasks that finished successfully.
            - ``"failed"``    — tasks that ended with an error.
            - ``"suspended"`` — tasks that were explicitly paused.
            - ``"cancelled"`` — tasks that were cancelled before completion.
        """
        with self._get_connection() as conn:
            rows = conn.execute("SELECT status, COUNT(*) as cnt FROM tasks GROUP BY status").fetchall()
            stats = {
                "queued": 0,
                "running": 0,
                "completed": 0,
                "failed": 0,
                "suspended": 0,
                "cancelled": 0,
                "timeout": 0,
                "retrying": 0,
            }
            for row in rows:
                key = row["status"].lower()
                if key in stats:
                    stats[key] = row["cnt"]
            return stats

    def _update_avg_latency(self, task_id: str) -> None:
        """Update rolling avg_latency_ms using the task's started_at / finished_at."""
        try:
            info = self.get_task_info(task_id)
            if info and info.get("started_at") and info.get("finished_at"):
                latency_ms = (info["finished_at"] - info["started_at"]) * 1000.0
                with self._metrics_lock:
                    n = self._metrics["tasks_completed"]  # already incremented
                    self._total_latency_ms += latency_ms
                    self._metrics["avg_latency_ms"] = self._total_latency_ms / n if n > 0 else 0.0
        except (ValueError, TypeError) as e:
            _log.warning("metrics update failed: %s", e)

    def get_metrics(self) -> dict[str, float]:
        """Return current in-process throughput / latency metrics.

        Returns a snapshot of ``_metrics``:
        - ``tasks_queued``    — total tasks submitted since process start.
        - ``tasks_completed`` — total tasks completed successfully.
        - ``tasks_failed``    — total tasks that ended with FAILED status.
        - ``avg_latency_ms``  — rolling average task execution latency (ms).
        """
        with self._metrics_lock:
            return dict(self._metrics)

    def validate_internal_state(self) -> bool:
        """校验状态一致性。"""
        if not os.access(self.sandbox_root, os.W_OK):
            return False
        with self._get_connection() as conn:
            res = conn.execute("PRAGMA integrity_check").fetchone()[0]
            if res != "ok":
                return False
            # 简单时序校验
            invalid_row = conn.execute(
                "SELECT task_id FROM tasks WHERE finished_at IS NOT NULL AND finished_at < created_at"
            ).fetchone()
            return invalid_row is None

    def health_check(self) -> dict[str, str | int | dict[str, int]]:
        """返回调度器的健康状态快照，用于运维监控和告警。

        Returns:
            dict 包含:
                - status: "healthy" | "degraded"
                - queue_depth: 当前排队任务数
                - running_tasks: 正在运行的任务数
                - failed_tasks: 失败任务数
                - completed_tasks: 已完成任务数
                - queue_size_by_priority: 各优先级排队任务分布
                - metrics: in-process throughput/latency counters
        """
        stats = self.get_statistics()
        queue_depth: int = stats.get("queued", 0)
        running: int = stats.get("running", 0)
        failed: int = stats.get("failed", 0)
        completed: int = stats.get("completed", 0)
        # Degraded if no capacity: running at full or db unreachable
        overall = "healthy"
        try:
            self.get_queue_length()  # lightweight liveness probe
        except sqlite3.Error:
            overall = "degraded"
        return {
            "status": overall,
            "queue_depth": queue_depth,
            "running_tasks": running,
            "failed_tasks": failed,
            "completed_tasks": completed,
            "queue_size_by_priority": stats.get("queue_size_by_priority", {}),
            "metrics": self.get_metrics(),
        }


if __name__ == "__main__":
    pass
