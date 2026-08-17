"""MOS agent_belief — 心智模型三表 (ADR-0396 Keystone).

BET-Y1Q1-T3-01: world_snapshot / capability_calibration / decision_outcome.
持久化通过 MOS 现有 write/recall 基础设施 (Neo4j or TemporalShadow).

使用方式:
    from mos.agent_belief import write_world_snapshot, recall_world_snapshot
    write_world_snapshot({"domain": "work", "key": "卫健委报告格式", "value": "三段式"})
    snapshots = recall_world_snapshot(domain="work", limit=10)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass
class WorldSnapshot:
    """世界快照 — 系统对世界的认知 (world_snapshot 表)."""
    domain: str  # work | family | health | finance | education
    key: str  # 认知键, e.g. "卫健委报告格式"
    value: Any  # 认知值, e.g. "三段式: 基本情况/主要做法/存在问题"
    source: str = ""  # 来源, e.g. "wpsnote:xxx" or "manual"
    confidence: float = 0.5  # 置信度 0-1
    ts: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


@dataclass
class CapabilityCalibration:
    """能力校准 — trust score 和性能指标 (capability_calibration 表)."""
    action_type: str  # 动作类型, e.g. "forward_notice"
    context_tag: str = ""  # 上下文标签, e.g. "routine" or "novel"
    trust_score: float = 0.5  # 信任分数 0-1
    total_executions: int = 0
    acceptance_rate: float = 0.0  # accepted / total
    last_5_outcomes: list[str] = field(default_factory=list)  # ["accepted", "revised", ...]
    ts: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


@dataclass
class DecisionOutcome:
    """决策结果 — 历史决策记录 (decision_outcome 表)."""
    scene_id: str  # 场景ID
    run_id: str  # journey run ID
    action: str  # 执行的动作
    adjudication: str  # accepted | rejected | revised
    actor: str = "system"  # 裁决者
    notes: str = ""  # 备注
    revision_diff: str = ""  # 如果revised, 改了什么
    ts: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


# ── Write functions (through MOS infrastructure) ──────────────────

def write_world_snapshot(snapshot: WorldSnapshot | dict) -> dict[str, Any]:
    """写入世界快照. 实际持久化通过MOS MemoryOS.write()."""
    data = snapshot.__dict__ if isinstance(snapshot, WorldSnapshot) else snapshot
    data["schema"] = "world_snapshot/v1"
    data["namespace"] = "agent_belief"
    return data  # Caller passes to MemoryOS.write() or BOS


def write_capability_calibration(cal: CapabilityCalibration | dict) -> dict[str, Any]:
    """写入能力校准."""
    data = cal.__dict__ if isinstance(cal, CapabilityCalibration) else cal
    data["schema"] = "capability_calibration/v1"
    data["namespace"] = "agent_belief"
    return data


def write_decision_outcome(outcome: DecisionOutcome | dict) -> dict[str, Any]:
    """写入决策结果."""
    data = outcome.__dict__ if isinstance(outcome, DecisionOutcome) else outcome
    data["schema"] = "decision_outcome/v1"
    data["namespace"] = "agent_belief"
    return data


# ── Recall functions ──────────────────────────────────────────────

def recall_world_snapshot(*, domain: str | None = None, key: str | None = None,
                          limit: int = 20) -> list[dict[str, Any]]:
    """查询世界快照. 实际查询通过MOS MemoryOS.recall().

    Returns: list of snapshot dicts (empty if MOS not configured).
    """
    try:
        from mos.service import MemoryOS
        mos = MemoryOS()
        query = {"namespace": "agent_belief", "schema": "world_snapshot/v1"}
        if domain:
            query["domain"] = domain
        if key:
            query["key"] = key
        results = mos.recall(query)
        return results.records if hasattr(results, "records") else []
    except Exception:
        return []


def recall_capability_calibration(*, action_type: str | None = None,
                                  limit: int = 20) -> list[dict[str, Any]]:
    """查询能力校准."""
    try:
        from mos.service import MemoryOS
        mos = MemoryOS()
        query = {"namespace": "agent_belief", "schema": "capability_calibration/v1"}
        if action_type:
            query["action_type"] = action_type
        results = mos.recall(query)
        return results.records if hasattr(results, "records") else []
    except Exception:
        return []


def recall_decision_outcome(*, scene_id: str | None = None,
                            limit: int = 20) -> list[dict[str, Any]]:
    """查询决策结果."""
    try:
        from mos.service import MemoryOS
        mos = MemoryOS()
        query = {"namespace": "agent_belief", "schema": "decision_outcome/v1"}
        if scene_id:
            query["scene_id"] = scene_id
        results = mos.recall(query)
        return results.records if hasattr(results, "records") else []
    except Exception:
        return []


# ── Convenience: update trust score from outcome ─────────────────

def update_trust_from_outcome(action_type: str, adjudication: str) -> float:
    """根据决策结果更新trust score (贝叶斯更新).

    accepted → trust += 0.02 (capped at 0.99)
    revised → trust unchanged (needs improvement)
    rejected → trust -= 0.05 (capped at 0.01)
    """
    existing = recall_capability_calibration(action_type=action_type, limit=1)
    current = existing[0]["trust_score"] if existing else 0.5

    if adjudication == "accepted":
        current = min(current + 0.02, 0.99)
    elif adjudication == "rejected":
        current = max(current - 0.05, 0.01)
    # revised: no change

    return current


__all__ = [
    "WorldSnapshot",
    "CapabilityCalibration",
    "DecisionOutcome",
    "write_world_snapshot",
    "write_capability_calibration",
    "write_decision_outcome",
    "recall_world_snapshot",
    "recall_capability_calibration",
    "recall_decision_outcome",
    "update_trust_from_outcome",
]
