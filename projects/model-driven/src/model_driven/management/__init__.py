"""
model_driven.management — 管理面

提供 Spec + ADR + OKR + OMO + 多Agent 协作的完整管理能力。
"""

from .adr import ADR, ADRManager, ADRStatus
from .agent_collab import AgentCollabManager, CollabTask, CollabTaskStatus
from .okr import OKR, OKRDecomposer, OKRManager, OKRStatus
from .omo_bridge import OMOBridge, OMOEvent, OMOEventType
from .spec import Spec, SpecManager, SpecStatus

__all__ = [
    # Spec
    "Spec",
    "SpecManager",
    "SpecStatus",
    # ADR
    "ADR",
    "ADRManager",
    "ADRStatus",
    # OKR
    "OKR",
    "OKRManager",
    "OKRStatus",
    # OMO Bridge
    "OMOBridge",
    "OMOEvent",
    "OMOEventType",
    # Agent Collab
    "AgentCollabManager",
    "CollabTask",
    "CollabTaskStatus",
]
