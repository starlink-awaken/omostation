from __future__ import annotations

"""
Extracted from SharedBrain D_Harvest → minerva.

---
Type: Module
Status: ACTIVE
Version: 1.0.0
Authority: nucleus/Z-Core/L0-Genome/R0-ACT-SYS-AX01-10_holographic_metadata_axiom.md
Layer: L3
---
"""
# Vector Pipeline ≡ Pipeline
# 内涵 ≝ {Vector, Pipeline}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, VectorPipeline)}
# 功能 ⊢ {Vector_Pipeline, Init_Vector, Validate_Pipeline}
# =============================================================================

# ---
# domain: D-Harvest
# layer: index
# status: active
# ---
"""
向量嵌入流水线

提供高性能、容错的向量嵌入生成和索引服务。
"""

import asyncio
import logging
import pickle
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import numpy as np

_log = logging.getLogger(__name__)


@dataclass
class EmbeddingResult:
    """嵌入结果"""

    item_id: int
    success: bool
    embedding: np.ndarray | None = None
    error: str | None = None
    duration_ms: float = 0.0


@dataclass
class PipelineStats:
    """流水线统计"""

    total_processed: int = 0
    successful: int = 0
    failed: int = 0
    retried: int = 0
    total_duration_ms: float = 0.0
    avg_duration_ms: float = 0.0
    last_update: str = ""

    def update(self, result: EmbeddingResult) -> None:
        """更新统计"""
        self.total_processed += 1
        if result.success:
            self.successful += 1
        else:
            self.failed += 1
        self.total_duration_ms += result.duration_ms
        self.avg_duration_ms = self.total_duration_ms / self.total_processed
        self.last_update = datetime.now(UTC).isoformat()


class _EmbeddingAdapter:
    """将 minerva EmbeddingProvider 适配为 VectorPipeline 所需的接口"""

    def __init__(self, provider: Any) -> None:
        self._provider = provider

    async def get_embedding(self, text: str) -> np.ndarray:
        embeddings = await self._provider.embed([text])
        return np.array(embeddings[0])

    def get_stats(self) -> dict:
        return {"provider": type(self._provider).__name__}


class VectorEmbeddingPipeline:
    """
    向量嵌入流水线

    特性：
    - 批处理优化
    - 错误重试
    - 回退策略
    - 性能监控
    """

    def __init__(
        self,
        batch_size: int = 50,
        max_retries: int = 3,
        retry_delay_ms: int = 100,
        timeout_ms: int = 30000,
        enable_fallback: bool = True,
    ) -> None:
        """
        初始化向量嵌入流水线

        Args:
            batch_size: 批处理大小
            max_retries: 最大重试次数
            retry_delay_ms: 重试延迟（毫秒）
            timeout_ms: 超时时间（毫秒）
            enable_fallback: 是否启用回退策略
        """
        self._batch_size = batch_size
        self._max_retries = max_retries
        self._retry_delay = retry_delay_ms / 1000.0
        self._timeout = timeout_ms / 1000.0
        self._enable_fallback = enable_fallback

        self._adapter: _EmbeddingAdapter | None = None
        self._index_path = Path(".omc/cache/vectors")
        self._index_path.mkdir(parents=True, exist_ok=True)
        self._index_file = self._index_path / "vector_index.pkl"
        self._lock = asyncio.Lock()

        self._stats = PipelineStats()
        self._failed_items: dict[int, dict] = {}

    def _get_adapter(self) -> Any:
        """延迟初始化向量适配器（使用 minerva embeddings 提供者）"""
        if self._adapter is None:
            try:
                from minerva.embeddings.providers import FallbackEmbeddingProvider

                self._adapter = _EmbeddingAdapter(FallbackEmbeddingProvider())
            except ImportError:
                raise
        return self._adapter

    async def process_item(self, item_id: int, title: str, body: str, metadata: dict | None = None) -> EmbeddingResult:
        """
        处理单个条目

        Args:
            item_id: 条目ID
            title: 标题
            body: 正文
            metadata: 元数据

        Returns:
            嵌入结果
        """
        start_time = asyncio.get_running_loop().time()

        text = f"{title} {body}"

        for attempt in range(self._max_retries + 1):
            try:
                adapter = self._get_adapter()
                embedding = await asyncio.wait_for(adapter.get_embedding(text), timeout=self._timeout)

                duration_ms = (asyncio.get_running_loop().time() - start_time) * 1000

                result = EmbeddingResult(
                    item_id=item_id,
                    success=True,
                    embedding=embedding,
                    duration_ms=duration_ms,
                )

                # 保存到索引
                await self._save_to_index(item_id, embedding, title, body, metadata)

                self._stats.update(result)
                return result

            except (TimeoutError, RuntimeError, OSError) as e:
                _log.warning(
                    f"[VectorPipeline] Attempt {attempt + 1}/{self._max_retries} failed for item #{item_id}: {e}"
                )

                if attempt < self._max_retries:
                    await asyncio.sleep(self._retry_delay * (attempt + 1))
                    self._stats.retried += 1
                else:
                    # 所有重试都失败
                    duration_ms = (asyncio.get_running_loop().time() - start_time) * 1000
                    result = EmbeddingResult(
                        item_id=item_id,
                        success=False,
                        error=str(e),
                        duration_ms=duration_ms,
                    )

                    # 尝试回退策略
                    if self._enable_fallback:
                        await self._fallback_save(item_id, title, body, metadata)

                    self._stats.update(result)
                    self._failed_items[item_id] = {
                        "title": title,
                        "body": body,
                        "metadata": metadata,
                        "error": str(e),
                        "timestamp": datetime.now(UTC).isoformat(),
                    }

                    return result

        # 不应该到这里
        return EmbeddingResult(item_id=item_id, success=False, error="Unknown error")

    async def process_batch(self, items: list[tuple[int, str, str, dict | None]]) -> list[EmbeddingResult]:
        """
        批量处理条目

        Args:
            items: [(item_id, title, body, metadata), ...]

        Returns:
            嵌入结果列表
        """
        if not items:
            return []

        results = []

        # 分批处理
        for i in range(0, len(items), self._batch_size):
            batch = items[i : i + self._batch_size]

            # 并行处理批次内的条目
            tasks = [self.process_item(item_id, title, body, metadata) for item_id, title, body, metadata in batch]

            batch_results = await asyncio.gather(*tasks, return_exceptions=True)

            # 处理异常
            for j, result in enumerate(batch_results):
                if isinstance(result, Exception):
                    item_id = batch[j][0]
                    results.append(EmbeddingResult(item_id=item_id, success=False, error=str(result)))
                elif isinstance(result, EmbeddingResult):
                    results.append(result)

            # 批次间隔，避免过载
            if i + self._batch_size < len(items):
                await asyncio.sleep(0.01)

        return results

    async def _save_to_index(
        self, item_id: int, embedding: np.ndarray, title: str, body: str, metadata: dict | None
    ) -> None:
        """保存到索引"""
        async with self._lock:
            index = self._load_index()
            index[item_id] = {
                "embedding": embedding,
                "title": title,
                "body": body,
                "metadata": metadata or {},
                "timestamp": datetime.now(UTC).isoformat(),
            }
            self._save_index(index)

    async def _fallback_save(self, item_id: int, title: str, body: str, metadata: dict | None) -> None:
        """
        回退保存策略

        当正常嵌入生成失败时，使用确定性hash生成向量。
        虽然语义质量差，但能保证服务可用性。
        """
        try:
            import hashlib

            # SHA-256 hash → unit vector
            text = f"{title} {body}"
            digest = hashlib.sha256(text.encode("utf-8")).digest()

            # 扩展到目标维度
            vec_bytes = digest
            target_dim = 1536  # 默认维度; 见 DEFAULT_VECTOR_DIM
            while len(vec_bytes) < target_dim:
                vec_bytes += hashlib.sha256(vec_bytes).digest()

            # 转换为 float32
            raw = vec_bytes[:target_dim]
            vec = np.frombuffer(raw, dtype=np.uint8).astype(np.float32)
            vec = (vec / 127.5) - 1.0

            # L2 归一化
            norm = np.linalg.norm(vec)
            if norm > 0:
                vec = vec / norm

            await self._save_to_index(item_id, vec, title, body, metadata)
            _log.warning(f"[VectorPipeline] Used fallback embedding for item #{item_id}")

        except (AttributeError, OSError, RuntimeError, TypeError, ValueError) as e:
            _log.error(f"[VectorPipeline] Fallback save failed for item #{item_id}: {e}")

    def _load_index(self) -> dict:
        """加载向量索引"""
        try:
            with open(self._index_file, "rb") as f:
                return cast("dict[Any, Any]", pickle.load(f))  # noqa: S301
        except FileNotFoundError:
            return {}
        except (OSError, pickle.PickleError, ValueError) as e:
            _log.warning(f"[VectorPipeline] Failed to load index: {e}")
            return {}

    def _save_index(self, index: dict) -> None:
        """保存向量索引"""
        try:
            self._index_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self._index_file, "wb") as f:
                pickle.dump(index, f)
        except OSError as e:
            _log.error(f"[VectorPipeline] Failed to save index: {e}")
            raise

    def get_stats(self) -> dict[str, Any]:
        """获取统计信息"""
        index = self._load_index()
        adapter_stats: dict[str, Any] = {}
        if self._adapter:
            adapter_stats = self._adapter.get_stats()

        return {
            "pipeline": {
                "total_processed": self._stats.total_processed,
                "successful": self._stats.successful,
                "failed": self._stats.failed,
                "retried": self._stats.retried,
                "avg_duration_ms": round(self._stats.avg_duration_ms, 2),
                "last_update": self._stats.last_update,
            },
            "index": {
                "total_vectors": len(index),
                "index_file": str(self._index_file),
            },
            "adapter": adapter_stats,
            "failed_items": len(self._failed_items),
        }

    async def retry_failed(self, limit: int = 100) -> list[EmbeddingResult]:
        """
        重试失败的条目

        Args:
            limit: 最大重试数量

        Returns:
            重试结果
        """
        if not self._failed_items:
            return []

        items_to_retry = list(self._failed_items.items())[:limit]
        results = []

        for item_id, data in items_to_retry:
            result = await self.process_item(
                item_id=item_id,
                title=data.get("title", ""),
                body=data.get("body", ""),
                metadata=data.get("metadata"),
            )

            results.append(result)

            # 如果成功，从失败列表移除
            if result.success:
                del self._failed_items[item_id]

        return results

    def clear_failed(self) -> int:
        """清除失败记录"""
        count = len(self._failed_items)
        self._failed_items.clear()
        return count


# 全局单例
_global_pipeline: VectorEmbeddingPipeline | None = None


def get_vector_pipeline(
    batch_size: int = 50,
    force_new: bool = False,
) -> VectorEmbeddingPipeline:
    """
    获取全局向量流水线实例

    Args:
        batch_size: 批处理大小
        force_new: 是否强制创建新实例

    Returns:
        VectorEmbeddingPipeline 实例
    """
    global _global_pipeline

    if force_new or _global_pipeline is None:
        _global_pipeline = VectorEmbeddingPipeline(batch_size=batch_size)
        _log.info("[VectorPipeline] Created new global pipeline")

    return _global_pipeline
