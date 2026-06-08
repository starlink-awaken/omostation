"""RouteScheduler — 三层路由引擎 (Provider → Model → Node).

集成了 QuotaEngine 的配额感知、PricingRegistry 的定价、
和 RouterPipeline 的评分策略。

用法::

    from llm_gateway.route_scheduler import RouteScheduler, RouteStrategies

    scheduler = RouteScheduler()
    route = scheduler.select("写代码", model="gpt-4o")
    print(f"Route: {route.provider}/{route.model} ${route.cost}/1K")
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from .pricing import PricingRegistry
from .quota_engine import QuotaEngine

_log = logging.getLogger(__name__)


@dataclass
class Route:
    """一次路由决策的结果。"""

    provider: str = ""
    model: str = ""
    cost_per_1k_input: float = 0.0
    cost_per_1k_output: float = 0.0
    score: float = 0.0
    strategy: str = "balanced"
    quota_pct: float = 100.0
    quota_source: str = ""
    node_id: str = ""


class RouteStrategies:
    """路由策略权重配置。"""

    BALANCED = {"cost": 0.35, "quota": 0.35, "speed": 0.30}
    COST_FIRST = {"cost": 0.70, "quota": 0.20, "speed": 0.10}
    SPEED_FIRST = {"cost": 0.10, "quota": 0.10, "speed": 0.80}
    QUOTA_FIRST = {"cost": 0.10, "quota": 0.70, "speed": 0.20}

    @classmethod
    def get(cls, name: str) -> dict[str, float]:
        return getattr(cls, name.upper(), cls.BALANCED)


# 已知 Provider 的参考延迟 (ms) — 无真实数据时使用
_REF_LATENCY: dict[str, float] = {
    "deepseek": 800, "openai": 500, "anthropic": 600,
    "gemini": 900, "minimax": 1200, "kimi": 700,
    "openrouter": 1500, "siliconflow": 1000, "nvidia": 2000,
    "ollama": 200, "hitl": 5000,
}


class RouteScheduler:
    """三层路由: Provider 过滤 → 评分 → 模型绑定。

    集成:
      - QuotaEngine (真实可用性 + 实时配额)
      - PricingRegistry (模型定价)
      - 策略评分 (成本/速度/配额)
    """

    def __init__(self) -> None:
        self._quota = QuotaEngine()
        self._pricing = PricingRegistry()

    def select(
        self,
        task: str = "",
        model: str = "",
        strategy: str = "balanced",
    ) -> Route | None:
        """选择最优路由。

        Args:
            task: 任务描述 (用于能力匹配)
            model: 指定模型名称 (可选)
            strategy: 路由策略 (balanced / cost_first / speed_first / quota_first)

        Returns:
            ``Route`` 或 ``None`` (无可用 Provider 时)
        """
        weights = RouteStrategies.get(strategy)

        # 1. 获取所有 Provider 状态
        all_status = self._quota.get_all_status()

        # 2. Filter: 只保留可用的
        candidates = {
            p: s for p, s in all_status.items()
            if s.available and s.has_key
        }

        if not candidates:
            _log.warning("RouteScheduler: no available providers")
            return None

        # 3. Score each provider
        best_score = -1.0
        best_route: Route | None = None

        for provider, status in candidates.items():
            # Cost score: cheaper = higher
            cost_p = self._pricing.get_cost(model) if model else {"input": 0, "output": 0}
            max_cost = 0.1  # $0.1/1K reference
            cost_in = cost_p.get("input", 0.01)
            cost_score = max(0, 1.0 - (cost_in / max_cost)) if cost_in > 0 else 1.0

            # Quota score: more remaining = higher
            quota_score = status.quota_pct / 100.0 if status.quota_pct > 0 else 0.5

            # Speed score: faster = higher
            latency = _REF_LATENCY.get(provider, 1000)
            speed_score = max(0, 1.0 - (latency / 10000))

            # Weighted total
            total = (
                cost_score * weights["cost"]
                + quota_score * weights["quota"]
                + speed_score * weights["speed"]
            )

            if total > best_score:
                best_score = total
                best_route = Route(
                    provider=provider,
                    model=model or self._pricing.get_price("", provider) or "",
                    cost_per_1k_input=cost_p.get("input", 0),
                    cost_per_1k_output=cost_p.get("output", 0),
                    score=round(total, 3),
                    strategy=strategy,
                    quota_pct=status.quota_pct,
                    quota_source=status.quota_source,
                    node_id=f"{provider}-cloud",
                )

        return best_route

    def select_all(
        self,
        task: str = "",
        model: str = "",
        strategy: str = "balanced",
    ) -> list[Route]:
        """返回所有可用 Provider 的评分排序结果。"""
        weights = RouteStrategies.get(strategy)
        all_status = self._quota.get_all_status()
        candidates = {p: s for p, s in all_status.items() if s.available and s.has_key}

        routes = []
        for provider, status in candidates.items():
            cost_p = self._pricing.get_cost(model) if model else {"input": 0, "output": 0}
            cost_in = cost_p.get("input", 0.01)
            cost_score = max(0, 1.0 - (cost_in / 0.1)) if cost_in > 0 else 1.0
            quota_score = status.quota_pct / 100.0
            latency = _REF_LATENCY.get(provider, 1000)
            speed_score = max(0, 1.0 - (latency / 10000))
            total = cost_score * weights["cost"] + quota_score * weights["quota"] + speed_score * weights["speed"]

            routes.append(Route(
                provider=provider,
                model=model or "",
                cost_per_1k_input=cost_p.get("input", 0),
                cost_per_1k_output=cost_p.get("output", 0),
                score=round(total, 3),
                strategy=strategy,
                quota_pct=status.quota_pct,
                quota_source=status.quota_source,
            ))

        return sorted(routes, key=lambda r: r.score, reverse=True)
