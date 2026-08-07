"""omo_reputation.py — Agent 信誉画像 (BET-Y1Q2-T4-02).

闭环: decision_outcome + adjudication verdict → reputation score.
守 ADR-0372: 决策日志入 MOS.
依赖: T1-03 MOS 闭环引擎 (decision_outcome + adjudication → belief).

信誉维度:
- reliability: 决策被 accepted 的比率 (accepted / total_adjudicated)
- accuracy: 高置信度决策的正确率 (confidence >= 0.8 且 accepted)
- volume: 总决策数
- avg_confidence: 平均决策置信度
- rejection_rate: 被 rejected 的比率
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .omo_adjudication import AdjudicationStore
from .omo_belief import MOSBeliefManager


@dataclass
class ReputationProfile:
    """Agent 信誉画像."""

    agent_id: str
    total_decisions: int = 0
    total_adjudicated: int = 0
    accepted: int = 0
    modified: int = 0
    rejected: int = 0
    avg_confidence: float = 0.0
    reliability: float = 1.0
    accuracy: float = 1.0
    rejection_rate: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "total_decisions": self.total_decisions,
            "total_adjudicated": self.total_adjudicated,
            "accepted": self.accepted,
            "modified": self.modified,
            "rejected": self.rejected,
            "avg_confidence": round(self.avg_confidence, 3),
            "reliability": round(self.reliability, 3),
            "accuracy": round(self.accuracy, 3),
            "rejection_rate": round(self.rejection_rate, 3),
        }


def compute_reputation(
    mos: MOSBeliefManager,
    store: AdjudicationStore,
    agent_id: str = "",
) -> ReputationProfile:
    """从 MOS decision_outcomes + adjudications 推导信誉画像.

    Args:
        mos: MOSBeliefManager (decision_outcome 来源).
        store: AdjudicationStore (裁决记录来源).
        agent_id: 过滤特定 agent (空=全局).
    """
    state = mos._load_state()
    outcomes = state.get("decision_outcomes", [])

    if agent_id:
        outcomes = [o for o in outcomes if o.get("source_run_id", "") == agent_id]

    total_decisions = len(outcomes)
    do_ids = {o["id"] for o in outcomes}

    all_adjudications = store.query(limit=10000)
    relevant_adj = [a for a in all_adjudications if a.get("decision_id") in do_ids]

    accepted = sum(1 for a in relevant_adj if a.get("verdict") == "accepted")
    modified = sum(1 for a in relevant_adj if a.get("verdict") == "modified")
    rejected = sum(1 for a in relevant_adj if a.get("verdict") == "rejected")
    total_adjudicated = accepted + modified + rejected

    confidences = [_extract_confidence(o.get("actual_outcome", "")) for o in outcomes]
    confidences = [c for c in confidences if c > 0]
    avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

    reliability = accepted / total_adjudicated if total_adjudicated > 0 else 1.0
    rejection_rate = rejected / total_adjudicated if total_adjudicated > 0 else 0.0

    high_conf = [
        o for o in outcomes if _extract_confidence(o.get("actual_outcome", "")) >= 0.8
    ]
    high_conf_ids = {o["id"] for o in high_conf}
    high_conf_accepted = sum(
        1
        for a in relevant_adj
        if a.get("decision_id") in high_conf_ids and a.get("verdict") == "accepted"
    )
    high_conf_adjudicated = sum(
        1 for a in relevant_adj if a.get("decision_id") in high_conf_ids
    )
    accuracy = (
        high_conf_accepted / high_conf_adjudicated if high_conf_adjudicated > 0 else 1.0
    )

    return ReputationProfile(
        agent_id=agent_id or "global",
        total_decisions=total_decisions,
        total_adjudicated=total_adjudicated,
        accepted=accepted,
        modified=modified,
        rejected=rejected,
        avg_confidence=avg_confidence,
        reliability=reliability,
        accuracy=accuracy,
        rejection_rate=rejection_rate,
    )


def _extract_confidence(actual_outcome: str) -> float:
    """从 actual_outcome 字符串提取 confidence 值."""
    for part in actual_outcome.split():
        if part.startswith("confidence="):
            try:
                return float(part.split("=", 1)[1])
            except ValueError:
                pass
    return 0.0


__all__ = ["ReputationProfile", "compute_reputation"]
