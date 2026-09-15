"""Health-gov doc-cycle cartridge: 卫健公文全周期闭环.

Entry points:
  domain.health_gov.doc_pipeline       — register/draft/approve/dispatch/export/supervise
  domain.health_gov.test_doc_pipeline  — self-test (`uv run python -m ...`)
"""

from .doc_pipeline import (
    DECISIONS,
    KINDS,
    ActionItem,
    Approval,
    DraftOpinion,
    IncomingDoc,
    MeetingMinutes,
    approve,
    close_action,
    dispatch,
    draft_opinion,
    export_package,
    record_minutes,
    register_incoming,
    supervise,
    validate_redhead,
)

__all__ = [
    "DECISIONS",
    "KINDS",
    "ActionItem",
    "Approval",
    "DraftOpinion",
    "IncomingDoc",
    "MeetingMinutes",
    "approve",
    "close_action",
    "dispatch",
    "draft_opinion",
    "export_package",
    "record_minutes",
    "register_incoming",
    "supervise",
    "validate_redhead",
]
