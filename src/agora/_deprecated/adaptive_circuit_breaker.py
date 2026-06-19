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
# Adaptive Circuit Breaker ≡ Module
# 内涵 ≝ {Adaptive, Circuit, Breaker}
# 外延 ≝ {e | e ∈ Organs ∧ implements(e, AdaptiveCircuitBreaker)}
# 功能 ⊢ {Adaptive_Circuit, Circuit_Breaker, Breaker_Init}
# =============================================================================

"""
---
Type: Organ
Layer: L3
Domain: D-Gateway
Status: ACTIVE
Updated: "2026-04-02"
Summary: Adaptive circuit breaker with dynamic thresholds
---

Adaptive Circuit Breaker - 自适应熔断器

根据历史成功率动态调整阈值，实现更智能的熔断决策。
"""

import enum  # noqa: E402
import logging  # noqa: E402
import time  # noqa: E402
from dataclasses import dataclass  # noqa: E402
from typing import Any  # noqa: E402

logger = logging.getLogger(__name__)


class CBState(enum.Enum):
    """熔断器状态"""

    CLOSED = "closed"  # 正常
    OPEN = "open"  # 熔断
    HALF_OPEN = "half-open"  # 探测


@dataclass
class CBMetrics:
    """熔断器指标"""

    total_requests: int = 0
    success_count: int = 0
    failure_count: int = 0
    timeout_count: int = 0

    @property
    def success_rate(self) -> float:
        if self.total_requests == 0:
            return 1.0
        return self.success_count / self.total_requests

    @property
    def failure_rate(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return self.failure_count / self.total_requests


class AdaptiveCircuitBreaker:
    """自适应熔断器

    基于EWMA（指数加权移动平均）计算成功率，动态调整熔断阈值。

    Example:
        >>> cb = AdaptiveCircuitBreaker(name="api-gateway")
        >>>
        >>> if cb.can_execute():
        >>>     try:
        >>>         result = await call_api()
        >>>         cb.record_success()
        >>>     except Exception:
        >>>         cb.record_failure()
    """

    # 默认配置
    DEFAULT_FAILURE_THRESHOLD = 0.5  # 默认失败率阈值
    DEFAULT_SUCCESS_THRESHOLD = 0.9  # 成功率恢复阈值
    EWMA_ALPHA = 0.2  # EWMA平滑因子
    MIN_REQUESTS = 10  # 最小请求数才开始计算

    def __init__(
        self,
        name: str,
        base_failure_threshold: float = DEFAULT_FAILURE_THRESHOLD,
        base_success_threshold: float = DEFAULT_SUCCESS_THRESHOLD,
        open_duration_seconds: float = 30.0,
        half_open_max_requests: int = 3,
        window_size: int = 100,
    ) -> None:
        self.name = name

        # 基础阈值
        self.base_failure_threshold = base_failure_threshold
        self.base_success_threshold = base_success_threshold

        # 自适应阈值
        self.adaptive_failure_threshold = base_failure_threshold
        self.adaptive_success_threshold = base_success_threshold

        # 状态
        self.state = CBState.CLOSED
        self.open_until = 0.0
        self.half_open_requests = 0
        self.half_open_max_requests = half_open_max_requests

        # 指标
        self.metrics = CBMetrics()
        self.ewma_success_rate = 1.0  # EWMA成功率
        self.window_size = window_size

        # 历史记录（用于计算EWMA）
        self.request_history: list[bool] = []  # True=成功, False=失败

    def can_execute(self) -> bool:
        """检查是否可以执行请求"""
        now = time.monotonic()

        if self.state == CBState.CLOSED:
            return True

        if self.state == CBState.OPEN:
            if now >= self.open_until:
                # 进入半开状态
                self.state = CBState.HALF_OPEN
                self.half_open_requests = 0
                logger.info(f"[CB:{self.name}] State changed to HALF-OPEN")
                return True
            return False

        if self.state == CBState.HALF_OPEN:
            # 半开状态下限制请求数
            if self.half_open_requests < self.half_open_max_requests:
                self.half_open_requests += 1
                return True
            return False

        return True

    def record_success(self) -> None:
        """记录成功"""
        self.metrics.total_requests += 1
        self.metrics.success_count += 1
        self.request_history.append(True)

        # 限制历史记录大小
        if len(self.request_history) > self.window_size:
            self.request_history.pop(0)

        # 更新EWMA
        self._update_ewma(1.0)

        # 更新自适应阈值
        self._adapt_thresholds()

        # 状态转换
        if self.state == CBState.HALF_OPEN:
            # 半开状态下连续成功，关闭熔断
            self._close_circuit()
        elif self.state == CBState.OPEN:
            # 不应发生，但做保护
            self._close_circuit()

    def record_failure(self, is_timeout: bool = False) -> None:
        """记录失败"""
        self.metrics.total_requests += 1
        self.metrics.failure_count += 1

        if is_timeout:
            self.metrics.timeout_count += 1

        self.request_history.append(False)

        # 限制历史记录大小
        if len(self.request_history) > self.window_size:
            self.request_history.pop(0)

        # 更新EWMA
        self._update_ewma(0.0)

        # 检查是否需要熔断
        if self.state == CBState.CLOSED:
            if self._should_open():
                self._open_circuit()
        elif self.state == CBState.HALF_OPEN:
            # 半开状态下失败，重新熔断
            self._open_circuit()

    def record_timeout(self) -> None:
        """记录超时"""
        self.record_failure(is_timeout=True)

    def _update_ewma(self, value: float) -> None:
        """更新EWMA成功率"""
        self.ewma_success_rate = (
            self.EWMA_ALPHA * value + (1 - self.EWMA_ALPHA) * self.ewma_success_rate
        )

    def _adapt_thresholds(self) -> None:
        """调整自适应阈值"""
        # 根据EWMA成功率调整阈值
        ewma_rate = self.ewma_success_rate

        # 成功率高时，可以容忍更低的失败率（更严格）
        # 成功率低时，需要容忍更高的失败率（更宽松）

        if ewma_rate > 0.95:
            # 非常健康，使用最严格的阈值
            self.adaptive_failure_threshold = self.base_failure_threshold * 0.5
        elif ewma_rate > 0.9:
            # 健康，稍微严格
            self.adaptive_failure_threshold = self.base_failure_threshold * 0.7
        elif ewma_rate > 0.8:
            # 正常，使用基础阈值
            self.adaptive_failure_threshold = self.base_failure_threshold
        elif ewma_rate > 0.6:
            # 亚健康，放宽阈值
            self.adaptive_failure_threshold = self.base_failure_threshold * 1.5
        else:
            # 不健康，使用最宽松的阈值
            self.adaptive_failure_threshold = self.base_failure_threshold * 2.0

        # 限制阈值范围
        self.adaptive_failure_threshold = max(
            0.1, min(0.9, self.adaptive_failure_threshold)
        )

    def _should_open(self) -> bool:
        """判断是否应该熔断"""
        if self.metrics.total_requests < self.MIN_REQUESTS:
            return False

        # 使用自适应阈值
        return self.metrics.failure_rate > self.adaptive_failure_threshold

    def _open_circuit(self) -> None:
        """打开熔断器"""
        self.state = CBState.OPEN
        self.open_until = time.monotonic() + 30.0  # 30秒冷却
        logger.warning(
            f"[CB:{self.name}] Circuit OPENED! "
            f"Failure rate: {self.metrics.failure_rate:.2%}, "
            f"Threshold: {self.adaptive_failure_threshold:.2%}"
        )

    def _close_circuit(self) -> None:
        """关闭熔断器"""
        was_open = self.state != CBState.CLOSED
        self.state = CBState.CLOSED
        self.half_open_requests = 0

        if was_open:
            logger.info(
                f"[CB:{self.name}] Circuit CLOSED. Success rate: {self.metrics.success_rate:.2%}"
            )

    def get_status(self) -> dict:
        """获取熔断器状态"""
        return {
            "name": self.name,
            "state": self.state.value,
            "metrics": {
                "total": self.metrics.total_requests,
                "success": self.metrics.success_count,
                "failure": self.metrics.failure_count,
                "success_rate": self.metrics.success_rate,
                "failure_rate": self.metrics.failure_rate,
            },
            "adaptive": {
                "ewma_success_rate": self.ewma_success_rate,
                "failure_threshold": self.adaptive_failure_threshold,
                "base_failure_threshold": self.base_failure_threshold,
            },
        }


class CircuitBreakerRegistry:
    """熔断器注册表"""

    _instance = None
    _breakers: dict[str, AdaptiveCircuitBreaker] = {}

    @classmethod
    def get_or_create(cls, name: str, **kwargs: Any) -> AdaptiveCircuitBreaker:
        """获取或创建熔断器"""
        if name not in cls._breakers:
            cls._breakers[name] = AdaptiveCircuitBreaker(name=name, **kwargs)
        return cls._breakers[name]

    @classmethod
    def get_status_all(cls) -> dict[str, dict]:
        """获取所有熔断器状态"""
        return {name: cb.get_status() for name, cb in cls._breakers.items()}
