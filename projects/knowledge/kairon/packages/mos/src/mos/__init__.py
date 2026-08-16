"""Memory OS (MOS) control plane — ADR-0372."""

from mos.envelope import MemoryEnvelope, ValidationError, validate_envelope
from mos.events import CARD_UPDATED_URIS, is_card_updated_event
from mos.service import ForgetResult, KnowledgeRef, MemoryOS, RecallResult, WriteResult

__all__ = [
    "MemoryEnvelope",
    "MemoryOS",
    "RecallResult",
    "ForgetResult",
    "KnowledgeRef",
    "ValidationError",
    "WriteResult",
    "CARD_UPDATED_URIS",
    "is_card_updated_event",
    "validate_envelope",
]

# agent_belief 三表 (ADR-0396 Keystone) — 可选导入, MOS未配置时不阻断
try:
    from mos.agent_belief import (
        WorldSnapshot,
        CapabilityCalibration,
        DecisionOutcome,
        write_world_snapshot,
        write_capability_calibration,
        write_decision_outcome,
        recall_world_snapshot,
        recall_capability_calibration,
        recall_decision_outcome,
        update_trust_from_outcome,
    )
    __all__ += [
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
except ImportError:
    pass

__version__ = "0.5.0"
