#!/usr/bin/env python3
"""HITL 审批流引擎 — 场景卡意图审批与证据面板.

The HITL (Human-In-The-Loop) approval flow manages the lifecycle from
a pending intent through human review to approval/rejection with full
evidence tracking.

Flow:
  pending_intents → review_queue → approve/reject → evidence_receipt → task_binding

SSOT:  ecos/src/ecos/ssot/registry/scene-cards.yaml
Engine: bin/ssot/scene-card-approval-flow.py
"""

from __future__ import annotations

import importlib.util
import json
import sys
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class ApprovalReceipt:
    receipt_id: str = ""
    intent_id: str = ""
    scene_id: str = ""
    journey_id: str = ""
    decision: str = ""  # approved, rejected
    reviewer: str = ""
    note: str = ""
    created_at: str = ""
    evidence_snapshot: list[dict] = field(default_factory=list)


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def _load_engine(workspace_root: Path, filename: str, name: str):
    path = workspace_root / "bin" / "ssot" / filename
    spec = importlib.util.spec_from_file_location(name, str(path))
    if spec is None or spec.loader is None:
        raise ImportError(f"{filename} is unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _load_inbox(workspace_root: Path):
    return _load_engine(workspace_root, "scene-card-decision-inbox.py", "approval_inbox")


def _load_bridge(workspace_root: Path):
    return _load_engine(workspace_root, "scene-card-task-bridge.py", "approval_bridge")


def _receipts_path(workspace_root: Path) -> Path:
    p = workspace_root / ".omo" / "_approvals"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _receipt_path(workspace_root: Path, receipt_id: str) -> Path:
    return _receipts_path(workspace_root) / f"{receipt_id}.json"


def save_receipt(workspace_root: Path, receipt: ApprovalReceipt) -> None:
    p = _receipt_path(workspace_root, receipt.receipt_id)
    p.write_text(json.dumps(asdict(receipt), indent=2, ensure_ascii=False))


def load_receipt(workspace_root: Path, receipt_id: str) -> ApprovalReceipt | None:
    p = _receipt_path(workspace_root, receipt_id)
    if not p.exists():
        return None
    data = json.loads(p.read_text())
    return ApprovalReceipt(**data)


def list_receipts(workspace_root: Path) -> list[ApprovalReceipt]:
    receipts = []
    for f in sorted(_receipts_path(workspace_root).glob("receipt-*.json")):
        data = json.loads(f.read_text())
        receipts.append(ApprovalReceipt(**data))
    return receipts


# ── Review queue ──

def get_review_queue(workspace_root: Path) -> list[dict[str, Any]]:
    """Get all intents pending review across all scenes."""
    inbox = _load_inbox(workspace_root)
    scenes = inbox.list_scenes(workspace_root)
    queue: list[dict[str, Any]] = []
    for scene in scenes:
        for journey in scene.journeys:
            for intent in journey.intents:
                if intent.status == "pending":
                    # Build evidence snapshot
                    evidence = [
                        {"source": e.source, "action": e.action, "result": e.result, "timestamp": e.timestamp}
                        for e in intent.evidence
                    ]
                    queue.append({
                        "intent_id": intent.id,
                        "scene_id": scene.id,
                        "scene_name": scene.name,
                        "journey_id": journey.id,
                        "journey_name": journey.name,
                        "source": intent.source,
                        "raw_content": intent.raw_content[:200],
                        "priority": intent.priority,
                        "created_at": intent.created_at,
                        "evidence": evidence,
                        "evidence_count": len(evidence),
                    })
    # Sort by priority (P0 first), then by creation time
    priority_order = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
    queue.sort(key=lambda x: (priority_order.get(x["priority"], 99), x["created_at"]))
    return queue


def get_evidence_detail(workspace_root: Path, intent_id: str) -> dict[str, Any] | None:
    """Get full evidence detail for a specific intent."""
    inbox = _load_inbox(workspace_root)
    scenes = inbox.list_scenes(workspace_root)
    for scene in scenes:
        for journey in scene.journeys:
            for intent in journey.intents:
                if intent.id == intent_id:
                    evidence = [
                        {
                            "source": e.source,
                            "action": e.action,
                            "result": e.result,
                            "timestamp": e.timestamp,
                            "actor": e.actor,
                        }
                        for e in intent.evidence
                    ]
                    return {
                        "intent_id": intent.id,
                        "scene_id": scene.id,
                        "scene_name": scene.name,
                        "journey_id": journey.id,
                        "journey_name": journey.name,
                        "source": intent.source,
                        "raw_content": intent.raw_content,
                        "priority": intent.priority,
                        "status": intent.status,
                        "task_id": intent.task_id,
                        "created_at": intent.created_at,
                        "processed_at": intent.processed_at,
                        "evidence": evidence,
                        "evidence_count": len(evidence),
                    }
    return None


# ── Approval actions ──

def approve_intent(
    workspace_root: Path,
    intent_id: str,
    reviewer: str = "human",
    note: str = "",
    outcome_metric: str = "",
) -> dict[str, Any]:
    """Approve an intent: create receipt → create task binding → update status.

    Returns:
        Dict with receipt_id, binding_id, task_id, and status.
    """
    # Load evidence before approval
    evidence_detail = get_evidence_detail(workspace_root, intent_id)
    evidence_snapshot = evidence_detail.get("evidence", []) if evidence_detail else []

    # Create task binding
    bridge = _load_bridge(workspace_root)
    binding_result = bridge.approve_intent_and_create_task(
        workspace_root, intent_id=intent_id, outcome_metric=outcome_metric,
    )
    if not binding_result["ok"]:
        return binding_result

    # Create approval receipt
    receipt = ApprovalReceipt(
        receipt_id=_new_id("receipt"),
        intent_id=intent_id,
        scene_id=evidence_detail.get("scene_id", "") if evidence_detail else "",
        journey_id=evidence_detail.get("journey_id", "") if evidence_detail else "",
        decision="approved",
        reviewer=reviewer,
        note=note,
        created_at=_now_iso(),
        evidence_snapshot=evidence_snapshot,
    )
    save_receipt(workspace_root, receipt)

    return {
        "ok": True,
        "receipt_id": receipt.receipt_id,
        "binding_id": binding_result["binding_id"],
        "task_id": binding_result["task_id"],
        "status": "approved",
        "reviewer": reviewer,
    }


def reject_intent(
    workspace_root: Path,
    intent_id: str,
    reviewer: str = "human",
    note: str = "",
) -> dict[str, Any]:
    """Reject an intent: update status → create receipt.

    Returns:
        Dict with receipt_id and status.
    """
    # Load evidence before rejection
    evidence_detail = get_evidence_detail(workspace_root, intent_id)
    evidence_snapshot = evidence_detail.get("evidence", []) if evidence_detail else []

    # Update intent status to rejected
    inbox = _load_inbox(workspace_root)
    intent = inbox.update_intent_status(
        workspace_root, intent_id=intent_id,
        new_status="rejected", actor=reviewer,
    )
    if intent is None:
        return {"ok": False, "error": f"Intent {intent_id} not found"}

    # Create rejection receipt
    receipt = ApprovalReceipt(
        receipt_id=_new_id("receipt"),
        intent_id=intent_id,
        scene_id=evidence_detail.get("scene_id", "") if evidence_detail else "",
        journey_id=evidence_detail.get("journey_id", "") if evidence_detail else "",
        decision="rejected",
        reviewer=reviewer,
        note=note,
        created_at=_now_iso(),
        evidence_snapshot=evidence_snapshot,
    )
    save_receipt(workspace_root, receipt)

    return {
        "ok": True,
        "receipt_id": receipt.receipt_id,
        "status": "rejected",
        "reviewer": reviewer,
    }


def get_approval_history(workspace_root: Path, limit: int = 20) -> list[dict[str, Any]]:
    """Get recent approval/rejection history."""
    receipts = list_receipts(workspace_root)
    receipts.sort(key=lambda r: r.created_at, reverse=True)
    return [
        {
            "receipt_id": r.receipt_id,
            "intent_id": r.intent_id,
            "scene_id": r.scene_id,
            "decision": r.decision,
            "reviewer": r.reviewer,
            "note": r.note,
            "created_at": r.created_at,
            "evidence_count": len(r.evidence_snapshot),
        }
        for r in receipts[:limit]
    ]


def get_approval_stats(workspace_root: Path) -> dict[str, Any]:
    """Get approval statistics."""
    inbox = _load_inbox(workspace_root)
    scenes = inbox.list_scenes(workspace_root)

    total = 0
    pending = 0
    approved = 0
    rejected = 0
    task_created = 0

    for scene in scenes:
        for journey in scene.journeys:
            for intent in journey.intents:
                total += 1
                if intent.status == "pending":
                    pending += 1
                elif intent.status == "approved" or intent.status == "task_created":
                    approved += 1
                elif intent.status == "rejected":
                    rejected += 1

    return {
        "total_intents": total,
        "pending_review": pending,
        "approved": approved,
        "rejected": rejected,
        "approval_rate": approved / total if total > 0 else 0.0,
        "receipts_count": len(list_receipts(workspace_root)),
    }
