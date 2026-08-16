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
# Downstream Trigger ≡ Module
# 内涵 ≝ {Downstream, Trigger}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, DownstreamTrigger)}
# 功能 ⊢ {Downstream_Trigger, Init_Downstream, Validate_Trigger}
# =============================================================================

# ---
# domain: D-Harvest
# layer: organ
# status: active
# -*-
"""
下游处理触发器
在 Markdown 文件写入后触发 D_KnowledgeIntegration 处理
"""

import asyncio
import logging
from pathlib import Path

_log = logging.getLogger(__name__)
_DOWNSTREAM_PROCESSING_ERRORS = (
    AttributeError,
    ImportError,
    OSError,
    RuntimeError,
    ValueError,
)


async def trigger_downstream_processing(md_file_path: Path) -> None:
    """
    触发下游处理流程

    当新的Markdown文件写入docs/docs/knowledge/目录后，自动触发：
    1. D_KnowledgeIntegration重新收割知识文件(更新索引)
    2. 通知系统知识库已更新

    Args:
        md_file_path: 新写入的 Markdown 文件路径
    """
    _log.info(f"Triggering downstream processing for: {md_file_path}")
    # Round 2: announce to bus-foundation before any actual work.
    _bus_emit_downstream(md_file_path, status="started")

    try:
        # 异步触发，不阻塞主流程
        await _process_downstream_async(md_file_path)
    except _DOWNSTREAM_PROCESSING_ERRORS as exc:
        _log.warning(f"Downstream processing failed for {md_file_path}: {exc}")
        _bus_emit_downstream(md_file_path, status="failed", error=str(exc))
    else:
        _bus_emit_downstream(md_file_path, status="completed")


async def _process_downstream_async(md_file_path: Path) -> None:
    """
    异步执行下游处理

    Args:
        md_file_path: 新写入的 Markdown 文件路径
    """
    # 注意：这里预留集成点
    # 实际的下游处理需要根据D_KnowledgeIntegration的具体API实现

    _log.info(f"Processing downstream for: {md_file_path}")

    # Stub: index update via D-KnowledgeIntegration harvester seam deferred
    # try:
    #     # 导入 KnowledgeHarvester 并执行 harvest()
    #
    #     harvester = KnowledgeHarvester(Path("docs/docs/knowledge/"))
    #     articles = harvester.harvest()
    #     _log.info(f"Updated index with {len(articles)} articles")
    # except ImportError:
    #     _log.warning("KnowledgeHarvester not available, skipping index update")

    # Stub: FactGraph incremental import via D-KnowledgeIntegration bridge deferred
    # try:
    #     # 导入 HarvestIntegrationBridge 并触发增量更新
    #
    #     # 触发FactGraph更新
    #     _log.info("Triggering FactGraph update")
    # except ImportError:
    #     _log.warning("HarvestIntegrationBridge not available, skipping FactGraph update")

    _log.info(f"Downstream processing completed for: {md_file_path}")


class DownstreamTrigger:
    """
    下游处理触发器类
    提供更灵活的触发配置和管理
    """

    def __init__(
        self,
        processing_delay_seconds: float = 1.0,
    ) -> None:
        """
        初始化下游触发器

        Args:
            processing_delay_seconds: 处理延迟(秒)，避免频繁触发
        """
        self.processing_delay = processing_delay_seconds
        self._last_processed: dict[str, float] = {}
        self._lock = asyncio.Lock()

    async def trigger(self, md_file_path: Path) -> None:
        """
        触发下游处理(带防抖)

        Args:
            md_file_path: 新写入的Markdown文件路径
        """
        file_key = str(md_file_path)

        async with self._lock:
            # 检查是否需要延迟处理
            import time

            now = time.time()
            last_time = self._last_processed.get(file_key, 0)

            if now - last_time < self.processing_delay:
                _log.debug(f"Skipping downstream trigger (too soon): {md_file_path}")
                return

            self._last_processed[file_key] = now

        # 延迟执行，避免阻塞
        await trigger_downstream_processing(md_file_path)


def get_downstream_trigger(
    processing_delay_seconds: float = 1.0,
) -> DownstreamTrigger:
    """
    工厂函数：获取下游触发器实例

    Args:
        processing_delay_seconds: 处理延迟

    Returns:
        DownstreamTrigger实例
    """
    return DownstreamTrigger(
        processing_delay_seconds=processing_delay_seconds,
    )


def _bus_emit_downstream(md_file_path: Path, status: str, error: str | None = None) -> None:
    """Best-effort bus-foundation emit for downstream events (Round 2).

    Topics: ``kairon:downstream:dispatched`` (status=started/completed)
            ``kairon:downstream:failed``      (status=failed)
    """
    try:
        from kairon_pipeline import bus_adapter
    except ImportError:
        return
    payload: dict = {
        "md_file": str(md_file_path),
        "status": status,
    }
    if error is not None:
        payload["error"] = error
    topic = "kairon:downstream:failed" if status == "failed" else "kairon:downstream:dispatched"
    try:
        bus_adapter.emit_event(
            event_type=topic,
            source="kairon-pipeline.downstream_trigger",
            payload=payload,
        )
    except Exception:  # defensive
        pass
