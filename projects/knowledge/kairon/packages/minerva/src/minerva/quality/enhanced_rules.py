from __future__ import annotations

"""
扩展质量规则 - 多维度知识质量评分

Extracted from SharedBrain D_Harvest → minerva.

新增评分维度:
- SourceCredibilityRule: 来源可信度评分
- ContentCompletenessRule: 内容完整性评分
- UsageFrequencyRule: 使用频率评分
- FreshnessRule: 时效性评分
- ReferenceQualityRule: 引用质量评分
"""

import logging
import math
import re
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from minerva.extractors.base import StructuredKnowledge
from minerva.quality.gate import IQualityRule

if TYPE_CHECKING:
    pass

_log = logging.getLogger(__name__)


# ============================================================================
# 使用频率跟踪器
# ============================================================================


@dataclass
class UsageStats:
    """知识使用统计"""

    uri: str
    access_count: int = 0
    last_accessed: float = field(default_factory=time.time)
    created_at: float = field(default_factory=time.time)
    search_matches: int = 0  # 被搜索匹配的次数
    injection_count: int = 0  # 被注入上下文的次数
    feedback_positive: int = 0  # 正面反馈次数
    feedback_negative: int = 0  # 负面反馈次数

    @property
    def age_hours(self) -> float:
        """知识年龄（小时）"""
        return (time.time() - self.created_at) / 3600

    @property
    def days_since_last_access(self) -> float:
        """距离上次访问的天数"""
        return (time.time() - self.last_accessed) / 86400

    @property
    def access_rate_per_day(self) -> float:
        """日均访问次数"""
        age_days = self.age_hours / 24
        if age_days < 0.01:  # 不足15分钟
            return float(self.access_count)
        return self.access_count / max(age_days, 0.1)


class UsageTracker:
    """使用频率跟踪器"""

    def __init__(self) -> None:
        self._stats: dict[str, UsageStats] = {}
        self._storage_path: str | None = None  # 可选持久化路径

    def record_access(self, uri: str, access_type: str = "view") -> None:
        """记录知识访问"""
        if uri not in self._stats:
            self._stats[uri] = UsageStats(uri=uri)

        stats = self._stats[uri]
        stats.access_count += 1
        stats.last_accessed = time.time()

        if access_type == "search":
            stats.search_matches += 1
        elif access_type == "injection":
            stats.injection_count += 1

    def record_feedback(self, uri: str, positive: bool) -> None:
        """记录用户反馈"""
        if uri not in self._stats:
            self._stats[uri] = UsageStats(uri=uri)

        stats = self._stats[uri]
        if positive:
            stats.feedback_positive += 1
        else:
            stats.feedback_negative += 1

    def get_stats(self, uri: str) -> UsageStats | None:
        """获取使用统计"""
        return self._stats.get(uri)

    def get_all_stats(self) -> dict[str, UsageStats]:
        """获取所有统计"""
        return self._stats.copy()

    def calculate_usage_score(self, uri: str) -> float:
        """
        计算使用频率分数 (0.0-1.0)

        考虑因素:
        - 访问频率
        - 最近访问时间
        - 搜索匹配度
        - 用户反馈
        """
        stats = self.get_stats(uri)
        if not stats:
            return 0.0  # 新知识无使用记录

        score = 0.0

        # 1. 访问频率 (0-0.4)
        # 日均访问 >10次得满分
        access_rate = stats.access_rate_per_day
        freq_score = min(access_rate / 10.0, 1.0) * 0.4
        score += freq_score

        # 2. 最近访问 (0-0.2)
        # 7天内访问过得分
        if stats.days_since_last_access < 1:
            score += 0.2
        elif stats.days_since_last_access < 7:
            score += 0.2 * (1 - stats.days_since_last_access / 7)

        # 3. 搜索匹配度 (0-0.2)
        # 搜索匹配率高说明知识相关性强
        if stats.access_count > 0:
            match_ratio = stats.search_matches / stats.access_count
            score += match_ratio * 0.2

        # 4. 用户反馈 (0-0.2)
        total_feedback = stats.feedback_positive + stats.feedback_negative
        if total_feedback > 0:
            positive_ratio = stats.feedback_positive / total_feedback
            score += positive_ratio * 0.2

        return min(score, 1.0)


# 全局单例
_global_usage_tracker: UsageTracker | None = None


def get_usage_tracker() -> UsageTracker:
    """获取全局使用跟踪器"""
    global _global_usage_tracker
    if _global_usage_tracker is None:
        _global_usage_tracker = UsageTracker()
    return _global_usage_tracker


# ============================================================================
# 扩展质量规则
# ============================================================================


class SourceCredibilityRule:
    """
    来源可信度规则

    根据知识来源评估可信度:
    - 官方文档/标准: 高分
    - 知名网站/博客: 中等分
    - 用户生成内容: 低分
    """

    # 可信来源域名列表
    TRUSTED_DOMAINS = {
        "docs.python.org",
        "developer.mozilla.org",
        "www.w3.org",
        "rust-lang.org",
        "go.dev",
        "nodejs.org",
        "docs.rs",
        "pytorch.org",
        "tensorflow.org",
    }

    # 中等可信域名
    MEDIUM_TRUST_DOMAINS = {
        "github.com",
        "stackoverflow.com",
        "medium.com",
        "dev.to",
        "habr.com",
        "juejin.cn",
    }

    def __init__(self) -> None:
        self.name = "source_credibility"

    async def evaluate(self, knowledge: StructuredKnowledge) -> float:
        source = knowledge.metadata.get("source", "") if knowledge.metadata else ""
        # 优先使用 knowledge.uri，然后检查 metadata
        uri = knowledge.uri or knowledge.metadata.get("uri", "") if knowledge.metadata else ""

        # 检查来源URL
        for domain in self.TRUSTED_DOMAINS:
            if domain in uri or domain in source:
                return 0.5  # 高可信度

        for domain in self.MEDIUM_TRUST_DOMAINS:
            if domain in uri or domain in source:
                return 0.3  # 中等可信度

        return 0.1  # 默认低可信度


class ContentCompletenessRule:
    """
    内容完整性规则

    检查内容的完整性:
    - 标题存在且有意义
    - 正文长度足够
    - 包含代码示例
    - 包含引用/链接
    """

    def __init__(self) -> None:
        self.name = "content_completeness"

    async def evaluate(self, knowledge: StructuredKnowledge) -> float:
        score = 0.0
        body = knowledge.body

        # 1. 标题质量 (0-0.25)
        if knowledge.title and len(knowledge.title) > 10:
            score += 0.15
            if len(knowledge.title) > 30:
                score += 0.1  # 描述性标题

        # 2. 内容长度 (0-0.25)
        length = len(body)
        if length > 200:
            score += 0.1
        if length > 1000:
            score += 0.15

        # 3. 代码示例 (0-0.25)
        code_blocks = re.findall(r"```[\w]*\n.*?```", body, re.DOTALL)
        if code_blocks:
            score += min(len(code_blocks) * 0.1, 0.25)

        # 4. 引用/链接 (0-0.25)
        # 检查是否有 markdown 链接或引用
        has_links = bool(re.search(r"\[.*?\]\(.*?\)", body))
        has_references = bool(re.search(r"参考|引用|see also|https?://", body, re.IGNORECASE))
        if has_links:
            score += 0.15
        if has_references:
            score += 0.1

        return min(score, 0.5)


class UsageFrequencyRule:
    """
    使用频率规则

    基于知识使用历史评分:
    - 访问频率
    - 最近访问时间
    - 搜索匹配度
    - 用户反馈
    """

    def __init__(self, usage_tracker: UsageTracker | None = None) -> None:
        self.name = "usage_frequency"
        self._tracker = usage_tracker or get_usage_tracker()

    async def evaluate(self, knowledge: StructuredKnowledge) -> float:
        # 优先使用 knowledge.uri，然后检查 metadata
        uri = knowledge.uri or (knowledge.metadata.get("uri", "") if knowledge.metadata else "")
        if not uri:
            return 0.0

        return self._tracker.calculate_usage_score(uri)


class FreshnessRule:
    """
    时效性规则

    根据知识新鲜度评分:
    - 最近创建/更新的知识得分更高
    - 考虑知识的"半衰期"
    """

    # 不同类型知识的半衰期（天）
    HALF_LIVES = {
        "api": 90,  # API文档90天后过时
        "tutorial": 180,  # 教程180天
        "concept": 365,  # 概念性内容1年
        "default": 270,  # 默认
    }

    def __init__(self) -> None:
        self.name = "freshness"

    async def evaluate(self, knowledge: StructuredKnowledge) -> float:
        # 获取时间戳
        metadata = knowledge.metadata or {}
        timestamp_str = metadata.get("timestamp") or metadata.get("created_at")

        if not timestamp_str:
            return 0.2  # 无时间戳，给默认分

        try:
            # 解析时间戳
            if isinstance(timestamp_str, (int, float)):
                created_at = datetime.fromtimestamp(timestamp_str, tz=UTC)
            else:
                created_at = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))

            age_days = (datetime.now(UTC) - created_at).days

            # 确定知识类型
            knowledge_type = metadata.get("type", "default").lower()
            half_life = self.HALF_LIVES.get(knowledge_type, self.HALF_LIVES["default"])

            # 计算新鲜度分数 (指数衰减)
            # 使用 e^(-t/HL) 公式，t=age_days, HL=half_life
            freshness = math.exp(-age_days / half_life)

            return freshness * 0.3

        except (ValueError, TypeError) as e:
            _log.warning(f"Failed to parse timestamp: {e}")
            return 0.1


class ReferenceQualityRule:
    """
    引用质量规则

    检查知识引用的质量:
    - 引用数量
    - 引用来源权威性
    - 引用格式规范性
    """

    def __init__(self) -> None:
        self.name = "reference_quality"

    async def evaluate(self, knowledge: StructuredKnowledge) -> float:
        body = knowledge.body
        score = 0.0

        # 1. 引用数量 (0-0.15)
        links = re.findall(r"\[.*?\]\((https?://[^\)]+)\)", body)
        if len(links) >= 3:
            score += 0.15
        elif len(links) >= 1:
            score += 0.08

        # 2. 引用权威性 (0-0.15)
        trusted_count = 0
        for url in links:
            for domain in SourceCredibilityRule.TRUSTED_DOMAINS:
                if domain in url:
                    trusted_count += 1
                    break

        if trusted_count >= 2:
            score += 0.15
        elif trusted_count >= 1:
            score += 0.08

        return min(score, 0.3)


# ============================================================================
# 组合质量评分器
# ============================================================================


class EnhancedQualityGate:
    """
    增强质量门控

    整合所有质量规则，提供更全面的评分:
    - 基础质量: LengthRule, LanguageRule, StructureRule, EncodingRule
    - 扩展质量: SourceCredibility, ContentCompleteness, UsageFrequency, Freshness, ReferenceQuality
    """

    def __init__(
        self,
        usage_tracker: UsageTracker | None = None,
        weights: dict[str, float] | None = None,
    ) -> None:
        """
        初始化增强质量门控

        Args:
            usage_tracker: 使用频率跟踪器
            weights: 各维度权重配置
        """
        self._tracker = usage_tracker or get_usage_tracker()

        # 默认权重
        self.weights: dict[str, float] = weights or {
            "source_credibility": 0.2,  # 来源可信度
            "content_completeness": 0.25,  # 内容完整性
            "usage_frequency": 0.25,  # 使用频率
            "freshness": 0.15,  # 时效性
            "reference_quality": 0.15,  # 引用质量
        }

        # 初始化规则
        self.rules: list[IQualityRule] = [
            SourceCredibilityRule(),
            ContentCompletenessRule(),
            UsageFrequencyRule(usage_tracker=self._tracker),
            FreshnessRule(),
            ReferenceQualityRule(),
        ]

    async def evaluate(self, knowledge: StructuredKnowledge) -> dict[str, float | bool]:
        """
        综合评估知识质量

        Returns:
            包含各维度分数和总分的字典
        """
        scores: dict[str, float | bool] = {}
        total_weighted_score = 0.0
        total_weight = 0.0

        for rule in self.rules:
            rule_name = rule.name
            rule_score = await rule.evaluate(knowledge)
            scores[rule_name] = rule_score

            weight = self.weights.get(rule_name, 0.2)
            total_weighted_score += rule_score * weight
            total_weight += weight

        # 归一化总分
        final_score = total_weighted_score / max(total_weight, 0.01)
        scores["total"] = min(final_score, 1.0)
        scores["passed"] = final_score >= 0.5  # 通过阈值

        return scores

    def record_access(self, uri: str, access_type: str = "view") -> None:
        """记录知识访问"""
        self._tracker.record_access(uri, access_type)

    def record_feedback(self, uri: str, positive: bool) -> None:
        """记录用户反馈"""
        self._tracker.record_feedback(uri, positive)

    def get_usage_stats(self, uri: str) -> UsageStats | None:
        """获取使用统计"""
        return self._tracker.get_stats(uri)


# ============================================================================
# 兼容性接口
# ============================================================================


# 为了向后兼容，将新规则也注册为 IQualityRule
class _CompatibilityWrapper:
    """将新规则包装为 IQualityRule 接口"""

    def __init__(self, rule: IQualityRule) -> None:
        self._rule = rule
        self._name = rule.name

    @property
    def name(self) -> str:
        return self._name

    async def evaluate(self, knowledge: StructuredKnowledge) -> float:
        return await self._rule.evaluate(knowledge)


def create_enhanced_rules() -> list[IQualityRule]:
    """创建兼容旧接口的增强规则列表"""
    return [
        _CompatibilityWrapper(SourceCredibilityRule()),
        _CompatibilityWrapper(ContentCompletenessRule()),
        _CompatibilityWrapper(UsageFrequencyRule()),
        _CompatibilityWrapper(FreshnessRule()),
        _CompatibilityWrapper(ReferenceQualityRule()),
    ]
