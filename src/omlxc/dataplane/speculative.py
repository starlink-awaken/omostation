"""Speculative Execution & Hybrid Routing Engine (ADR-0197).

Routes agent queries to local-first lightweight speculative models (8B/14B Q4_K_M)
or cascades to frontier cloud models based on task complexity, AST safety, and policy depth.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class SpeculativeRoutingDecision:
    target_tier: str  # "local" | "cloud" | "hybrid-speculative"
    recommended_model: str
    draft_model: str | None
    estimated_speedup_ratio: float
    reasoning: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_tier": self.target_tier,
            "recommended_model": self.recommended_model,
            "draft_model": self.draft_model,
            "estimated_speedup_ratio": self.estimated_speedup_ratio,
            "reasoning": self.reasoning,
        }


class SpeculativeRouter:
    """Evaluates task context and determines optimal local vs cloud speculative routing."""

    def __init__(self) -> None:
        pass

    def evaluate(self, prompt: str, domain: str = "general") -> SpeculativeRoutingDecision:
        text = prompt.strip()
        length = len(text)

        # 1. Check for quick AST / Syntax / Format tasks -> Local 8B/14B
        is_local_triage = length < 120 and not any(k in text for k in ["架构设计", "长远愿景", "博弈推演", "复杂重构", "红蓝对抗"])
        if is_local_triage:
            return SpeculativeRoutingDecision(
                target_tier="local",
                recommended_model="qwen2.5-coder:14b",
                draft_model="qwen2.5-coder:7b",
                estimated_speedup_ratio=2.8,
                reasoning="任务特征属于高频结构化/语法分诊类，由本地 14B Q4_K_M 模型独占处理，0 成本且 0 隐私泄露。",
            )

        # 2. Check for complex strategic / architectural / multi-perspective tasks -> Hybrid Speculative or Cloud
        is_deep_reasoning = any(k in text for k in ["架构", "愿景", "长远", "推演", "博弈", "审计", "合规", "红蓝对抗", "立项方案"])
        if is_deep_reasoning or length > 500:
            return SpeculativeRoutingDecision(
                target_tier="hybrid-speculative",
                recommended_model="claude-3-5-sonnet / deepseek-r1",
                draft_model="qwen2.5-coder:14b",
                estimated_speedup_ratio=1.9,
                reasoning="涉及深层架构规划与政策博弈推演，启用本地 14B 投机草稿生成 + 云端 Frontier 模型核验级联。",
            )

        # 3. Default general task
        return SpeculativeRoutingDecision(
            target_tier="local",
            recommended_model="qwen2.5-coder:14b",
            draft_model=None,
            estimated_speedup_ratio=1.5,
            reasoning="常规领域任务，优先分配本地算力底座处理。",
        )
