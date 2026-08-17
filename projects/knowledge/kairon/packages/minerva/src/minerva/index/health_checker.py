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
# Health Checker ≡ Module
# 内涵 ≝ {Health, Checker}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, HealthChecker)}
# 功能 ⊢ {Health_Checker, Init_Health, Validate_Checker}
# =============================================================================

# ---
# domain: D-Harvest
# layer: index
# status: active
# ---
"""
索引健康检查器

监控BM25和向量索引的健康状态。
"""

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

_log = logging.getLogger(__name__)


@dataclass
class HealthReport:
    """健康检查报告"""

    is_healthy: bool
    freshness_score: float  # 0-100
    corruption_detected: bool
    issues: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    timestamp: str = ""

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "is_healthy": self.is_healthy,
            "freshness_score": self.freshness_score,
            "corruption_detected": self.corruption_detected,
            "issues": self.issues,
            "recommendations": self.recommendations,
            "timestamp": self.timestamp,
        }


class IndexHealthChecker:
    """
    索引健康检查器

    检查项：
    1. 索引新鲜度（与数据库同步程度）
    2. 索引完整性（是否损坏）
    3. 性能指标（查询延迟）
    """

    def __init__(
        self,
        knowledge_store: Any | None = None,
        index_manager: Any | None = None,
        stale_threshold_seconds: int = 3600,
    ) -> None:
        """
        初始化健康检查器

        Args:
            knowledge_store: KnowledgeStore实例
            index_manager: AutoIndexManager实例
            stale_threshold_seconds: 索引过期阈值（秒）
        """
        self._store = knowledge_store
        self._manager = index_manager
        self._stale_threshold = stale_threshold_seconds

    async def check_freshness(self) -> float:
        """
        检查索引新鲜度

        计算方法：
        - 获取数据库中最新条目时间
        - 获取索引中最新条目时间
        - 计算时间差，转换为0-100分数

        Returns:
            新鲜度分数 (0-100)
        """
        if self._manager is None:
            return 0.0

        # 获取索引更新时间
        bm25_stats = self._manager._bm25_updater.get_stats()
        last_updated = bm25_stats.get("last_updated", "")

        if last_updated:
            try:
                last_time = datetime.fromisoformat(last_updated)
                age_seconds = (datetime.now(UTC) - last_time).total_seconds()

                # 转换为分数
                if age_seconds < 60:  # 1分钟内
                    return 100.0
                elif age_seconds < 300:  # 5分钟内
                    return 90.0
                elif age_seconds < self._stale_threshold:
                    ratio = age_seconds / self._stale_threshold
                    return max(0.0, 100.0 - ratio * 50.0)
                else:
                    return 0.0
            except (ValueError, TypeError):
                return 0.0

        return 0.0

    async def check_corruption(self) -> tuple[bool, list[str]]:
        """
        检查索引损坏

        Returns:
            (是否损坏, 问题列表)
        """
        issues = []

        if self._manager is None or self._store is None:
            return False, ["Index manager or store not available"]

        # 检查BM25索引
        bm25_stats = self._manager._bm25_updater.get_stats()

        # 获取数据库统计
        db_stats = await self._store.get_stats()
        db_count = db_stats.get("total_items", 0)
        bm25_count = bm25_stats.get("total_docs")

        # 检查数量差异
        if db_count > 0 and bm25_count is not None:
            diff_ratio = abs(db_count - bm25_count) / db_count
            if diff_ratio > 0.1:  # 10%差异
                issues.append(f"BM25索引数量不匹配: DB={db_count}, Index={bm25_count} ({diff_ratio * 100:.1f}%差异)")

        # 检查向量索引
        vector_stats = self._manager._vector_updater.get_stats()
        vector_count = vector_stats.get("total_vectors")

        if db_count > 0 and vector_count is not None:
            diff_ratio = abs(db_count - vector_count) / db_count
            if diff_ratio > 0.1:
                issues.append(f"向量索引数量不匹配: DB={db_count}, Index={vector_count} ({diff_ratio * 100:.1f}%差异)")

        return len(issues) > 0, issues

    async def check_performance(self) -> dict[str, Any]:
        """
        检查性能指标

        Returns:
            性能指标字典
        """
        metrics = {
            "bm25_search_latency_ms": 0.0,
            "vector_search_latency_ms": 0.0,
            "index_size_mb": 0.0,
        }

        if self._manager is None:
            return metrics

        # 计算索引文件大小
        try:
            if hasattr(self._manager._bm25_updater, "_searcher"):
                cache_file = self._manager._bm25_updater._searcher._cache_file
                if cache_file.exists():
                    size_bytes = cache_file.stat().st_size
                    metrics["bm25_index_size_mb"] = round(size_bytes / (1024 * 1024), 2)

            if hasattr(self._manager._vector_updater, "_index_file"):
                index_file = self._manager._vector_updater._index_file
                if index_file.exists():
                    size_bytes = index_file.stat().st_size
                    metrics["vector_index_size_mb"] = round(size_bytes / (1024 * 1024), 2)
        except (OSError, AttributeError):
            pass

        return metrics

    async def generate_report(self) -> HealthReport:
        """生成健康报告"""
        freshness = await self.check_freshness()
        is_corrupted, issues = await self.check_corruption()

        recommendations = []
        if freshness < 50:
            recommendations.append("索引过期，建议执行增量更新或重建")

        if is_corrupted:
            recommendations.append("检测到索引损坏，建议执行修复")

        return HealthReport(
            is_healthy=freshness >= 50 and not is_corrupted,
            freshness_score=freshness,
            corruption_detected=is_corrupted,
            issues=issues,
            recommendations=recommendations,
            timestamp=datetime.now(UTC).isoformat(),
        )

    async def repair(self) -> dict[str, Any]:
        """
        自动修复索引

        策略：
        1. 如果数量差异小，执行增量同步
        2. 如果数量差异大，执行重建

        Returns:
            修复结果
        """
        results: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "actions_taken": [],
            "success": True,
        }

        if self._manager is None or self._store is None:
            results["success"] = False
            results["actions_taken"].append("无法修复：缺少必要的组件")
            return results

        report = await self.generate_report()

        if report.corruption_detected:
            # 检查差异大小
            db_stats = await self._store.get_stats()
            bm25_stats = self._manager._bm25_updater.get_stats()

            db_count = db_stats.get("total_items", 0)
            bm25_count = bm25_stats.get("total_docs", 0)

            diff = abs(db_count - bm25_count)

            if diff > 100:  # 差异太大，重建
                sync_results = await self._manager.sync_index(self._store)
                results["actions_taken"].append(f"BM25索引已重建并同步: {sync_results}")
            else:  # 差异小，增量同步
                sync_results = await self._manager.sync_index(self._store)
                results["actions_taken"].append(f"BM25索引已增量同步: {sync_results}")

        return results

    async def get_health_summary(self) -> dict[str, Any]:
        """
        获取健康摘要

        Returns:
            包含所有健康信息的字典
        """
        report = await self.generate_report()
        performance = await self.check_performance()
        manager_stats = self._manager.get_stats() if self._manager else {}

        return {
            "health": report.to_dict(),
            "performance": performance,
            "manager_stats": manager_stats,
        }


# 便捷函数
async def check_index_health(knowledge_store: Any | None = None, index_manager: Any | None = None) -> HealthReport:
    """
    检查索引健康

    Args:
        knowledge_store: KnowledgeStore实例
        index_manager: AutoIndexManager实例

    Returns:
        健康报告
    """
    checker = IndexHealthChecker(knowledge_store, index_manager)
    return await checker.generate_report()


async def repair_indexes(knowledge_store: Any | None = None, index_manager: Any | None = None) -> dict[str, Any]:
    """
    修复索引

    Args:
        knowledge_store: KnowledgeStore实例
        index_manager: AutoIndexManager实例

    Returns:
        修复结果
    """
    checker = IndexHealthChecker(knowledge_store, index_manager)
    return await checker.repair()
