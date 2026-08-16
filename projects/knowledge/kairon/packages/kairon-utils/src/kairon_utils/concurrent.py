from __future__ import annotations

"""
---
Type: Module
Status: ACTIVE
Version: 1.0.0
Authority: nucleus/Z-Core/L0-Genome/R0-ACT-SYS-AX01-10_holographic_metadata_axiom.md
Layer: L3
---
"""
# =============================================================================
# 0. 形式化摘要 ≝
# =============================================================================
# Concurrent ≡ Module
# 内涵 ≝ {Concurrent}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, Concurrent)}
# 功能 ⊢ {Init_Concurrent, Execute_Concurrent, Validate_Concurrent}
# =============================================================================

# ---
# domain: D-Harvest
# layer: organ
# status: active
# ---

"""
并发工具模块 - 支持并行收割执行

提供并发控制、超时管理、错误聚合和结果收集功能。
"""
import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, TypeVar

T = TypeVar("T")
_log = logging.getLogger(__name__)

_CONCURRENT_OPERATIONAL_ERRORS = (
    AttributeError,
    ImportError,
    LookupError,
    OSError,
    RuntimeError,
    TypeError,
    ValueError,
)
_CONCURRENT_SUPPORTED_ERROR_MODULE_PREFIXES = (
    "asyncio",
    "builtins",
    "organs.D_Harvest",
    "sqlite3",
)


def _is_supported_concurrent_error(exc: BaseException) -> bool:
    module_name = type(exc).__module__
    return any(
        module_name == prefix or module_name.startswith(f"{prefix}.")
        for prefix in _CONCURRENT_SUPPORTED_ERROR_MODULE_PREFIXES
    )


@dataclass
class ConcurrentResult:
    """并发执行结果包装器"""

    success: bool
    data: Any = None
    error: Exception | None = None
    execution_time: float = 0.0
    source_id: str = ""


@dataclass
class ConcurrentBatchResult:
    """批量并发执行结果"""

    results: dict[str, ConcurrentResult] = field(default_factory=dict)
    total_time: float = 0.0
    success_count: int = 0
    failure_count: int = 0
    errors: list[tuple[str, Exception]] = field(default_factory=list)

    @property
    def all_succeeded(self) -> bool:
        """检查是否全部成功"""
        return self.failure_count == 0

    @property
    def success_rate(self) -> float:
        """计算成功率"""
        total = self.success_count + self.failure_count
        return self.success_count / total if total > 0 else 0.0


class ConcurrencyManager:
    """
    并发管理器 - 使用 Semaphore 控制并发数

    功能：
    - 限制并发任务数量
    - 支持超时控制
    - 错误聚合
    - 结果收集
    """

    def __init__(self, max_concurrent: int = 5) -> None:
        """
        初始化并发管理器

        Args:
            max_concurrent: 最大并发数（默认 5）
        """
        self.max_concurrent = max_concurrent
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._active_tasks: set[asyncio.Task] = set()

    async def execute(
        self, operation: Callable[[str], Awaitable[T]], source_id: str, timeout: float | None = None
    ) -> ConcurrentResult:
        """
        执行单个操作，受并发控制

        Args:
            operation: 异步操作函数
            source_id: 源标识符
            timeout: 超时时间（秒），None 表示无超时

        Returns:
            ConcurrentResult 包装结果
        """
        start_time = asyncio.get_event_loop().time()

        async with self._semaphore:
            try:
                # 创建任务
                task: asyncio.Task = asyncio.create_task(operation(source_id))  # type: ignore[arg-type]
                self._active_tasks.add(task)

                # 执行并处理超时
                if timeout:
                    result = await asyncio.wait_for(task, timeout=timeout)
                else:
                    result = await task

                execution_time = asyncio.get_event_loop().time() - start_time

                return ConcurrentResult(success=True, data=result, execution_time=execution_time, source_id=source_id)

            except TimeoutError as e:
                execution_time = asyncio.get_event_loop().time() - start_time
                _log.warning(f"Operation timeout for {source_id} after {timeout}s")
                return ConcurrentResult(success=False, error=e, execution_time=execution_time, source_id=source_id)

            except _CONCURRENT_OPERATIONAL_ERRORS as e:
                if not _is_supported_concurrent_error(e):
                    raise
                execution_time = asyncio.get_event_loop().time() - start_time
                _log.error(f"Operation failed for {source_id}: {e}")
                return ConcurrentResult(success=False, error=e, execution_time=execution_time, source_id=source_id)

            finally:
                self._active_tasks.discard(task)  # type: ignore[reportPossiblyUnboundVariable]

    async def execute_batch(
        self,
        operation: Callable[[str], Awaitable[T]],
        source_ids: list[str],
        timeout: float | None = None,
        per_source_timeout: float | None = None,
    ) -> ConcurrentBatchResult:
        """
        批量执行操作，并行处理

        Args:
            operation: 异步操作函数
            source_ids: 源标识符列表
            timeout: 整体超时时间（秒）
            per_source_timeout: 每个源的超时时间（秒）

        Returns:
            ConcurrentBatchResult 批量结果
        """
        batch_start = asyncio.get_event_loop().time()
        batch_result = ConcurrentBatchResult()

        # 创建所有任务
        tasks = [
            asyncio.create_task(self.execute(operation, source_id, per_source_timeout)) for source_id in source_ids
        ]

        try:
            # 使用 asyncio.gather 并行执行所有任务
            if timeout:
                # 整体超时控制
                results = await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=False), timeout=timeout)
            else:
                results = await asyncio.gather(*tasks, return_exceptions=False)

            # 处理结果
            for result in results:
                batch_result.results[result.source_id] = result
                if result.success:
                    batch_result.success_count += 1
                else:
                    batch_result.failure_count += 1
                    if result.error:
                        batch_result.errors.append((result.source_id, result.error))

        except TimeoutError:
            _log.error(f"Batch operation timeout after {timeout}s")
            # 取消所有未完成的任务
            for task in tasks:
                if not task.done():
                    task.cancel()
            # 等待取消完成
            await asyncio.gather(*tasks, return_exceptions=True)

        except _CONCURRENT_OPERATIONAL_ERRORS as e:
            if not _is_supported_concurrent_error(e):
                raise
            _log.error(f"Batch operation failed: {e}")
            batch_result.errors.append(("batch", e))

        batch_result.total_time = asyncio.get_event_loop().time() - batch_start
        _log.info(
            f"Batch completed: {batch_result.success_count} success, "
            f"{batch_result.failure_count} failed in {batch_result.total_time:.2f}s"
        )

        return batch_result

    async def execute_with_taskgroup(
        self,
        operation: Callable[[str], Awaitable[T]],
        source_ids: list[str],
        timeout: float | None = None,
        per_source_timeout: float | None = None,
    ) -> ConcurrentBatchResult:
        """
        使用 asyncio.TaskGroup 批量执行（Python 3.11+）

        Args:
            operation: 异步操作函数
            source_ids: 源标识符列表
            timeout: 整体超时时间（秒）
            per_source_timeout: 每个源的超时时间（秒）

        Returns:
            ConcurrentBatchResult 批量结果
        """
        batch_start = asyncio.get_event_loop().time()
        batch_result = ConcurrentBatchResult()

        try:
            # 使用 TaskGroup 自动处理异常传播
            async with asyncio.TaskGroup() as tg:
                tasks = []
                for source_id in source_ids:
                    task = tg.create_task(self.execute(operation, source_id, per_source_timeout))
                    tasks.append((source_id, task))

            # 收集结果
            for source_id, task in tasks:
                try:
                    result = task.result()
                    batch_result.results[source_id] = result
                    if result.success:
                        batch_result.success_count += 1
                    else:
                        batch_result.failure_count += 1
                        if result.error:
                            batch_result.errors.append((source_id, result.error))
                except _CONCURRENT_OPERATIONAL_ERRORS as e:
                    if not _is_supported_concurrent_error(e):
                        raise
                    batch_result.failure_count += 1
                    batch_result.errors.append((source_id, e))

        except* _CONCURRENT_OPERATIONAL_ERRORS as eg:
            supported_exceptions = [exc for exc in eg.exceptions if _is_supported_concurrent_error(exc)]
            unsupported_exceptions = [exc for exc in eg.exceptions if not _is_supported_concurrent_error(exc)]
            if supported_exceptions:
                _log.error(f"TaskGroup failed with exceptions: {tuple(supported_exceptions)}")
                batch_result.failure_count += len(supported_exceptions)
                batch_result.errors.extend(("taskgroup", exc) for exc in supported_exceptions)
            if unsupported_exceptions:
                raise ExceptionGroup("TaskGroup failed", unsupported_exceptions) from None

        batch_result.total_time = asyncio.get_event_loop().time() - batch_start
        return batch_result

    def get_active_count(self) -> int:
        """获取当前活跃任务数"""
        return len(self._active_tasks)

    async def wait_all(self, timeout: float | None = None) -> None:
        """
        等待所有活跃任务完成

        Args:
            timeout: 等待超时时间（秒）
        """
        if not self._active_tasks:
            return

        try:
            await asyncio.wait_for(asyncio.gather(*self._active_tasks, return_exceptions=True), timeout=timeout)
        except TimeoutError:
            _log.warning(f"Wait all timeout after {timeout}s")


class ProgressTracker:
    """
    进度跟踪器 - 跟踪并行收割进度
    """

    def __init__(self, total: int) -> None:
        """
        初始化进度跟踪器

        Args:
            total: 总任务数
        """
        self.total = total
        self.completed = 0
        self.succeeded = 0
        self.failed = 0
        self._lock = asyncio.Lock()

    async def record_success(self) -> None:
        """记录成功"""
        async with self._lock:
            self.completed += 1
            self.succeeded += 1

    async def record_failure(self) -> None:
        """记录失败"""
        async with self._lock:
            self.completed += 1
            self.failed += 1

    @property
    def progress_percentage(self) -> float:
        """计算进度百分比"""
        return (self.completed / self.total * 100) if self.total > 0 else 0.0

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "total": self.total,
            "completed": self.completed,
            "succeeded": self.succeeded,
            "failed": self.failed,
            "progress_percentage": self.progress_percentage,
            "remaining": self.total - self.completed,
        }


async def gather_with_concurrency(max_concurrent: int, *tasks: asyncio.Task) -> list:
    """
    带并发限制的 gather 函数

    Args:
        max_concurrent: 最大并发数
        *tasks: 任务列表

    Returns:
        任务结果列表
    """
    semaphore = asyncio.Semaphore(max_concurrent)

    async def _bounded_task(task: asyncio.Task) -> Any:
        async with semaphore:
            return await task

    return await asyncio.gather(*(_bounded_task(task) for task in tasks))
