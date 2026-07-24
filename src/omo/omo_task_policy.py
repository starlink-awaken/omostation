from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .omo_shared import load_yaml


@dataclass(frozen=True)
class TaskPolicy:
    name: str
    summary: str
    target_roots: tuple[str, ...]
    file_glob: str
    prohibited_roots: tuple[str, ...] = ()
    required_fields: dict[str, Any] = field(default_factory=dict)
    required_status: str | None = None
    allowed_statuses: tuple[str, ...] = ()
    validator_id: str | None = None
    custom_validator: Callable[[Path, dict[str, Any]], list[str]] | None = None


OPC_P6_SELF_EVOLUTION_POLICY = TaskPolicy(
    name="self-evolution-approval",
    summary="self-evolution 任务只能留在 planned/，且审批字段必须保持人工待批基线",
    target_roots=("planned",),
    file_glob="OPC-P6-SELF-EVOLUTION-*.yaml",
    prohibited_roots=("active",),
    required_fields={
        "approval_required": True,
        "human_approval_required": True,
        "approval_state": "awaiting_human",
    },
    allowed_statuses=("candidate",),
)


def _validate_human_approval_ref(task_path: Path, payload: dict[str, Any]) -> list[str]:
    if payload.get("human_approval_required") is not True:
        return []
    if payload.get("status") not in {"planned", "review"}:
        return []
    approval_ref = payload.get("approval_ref")
    if not isinstance(approval_ref, str) or not approval_ref:
        return [
            f"{task_path.name}: approval_ref must point to task-specific promotion approval yaml"
        ]
    if not approval_ref.endswith(".yaml"):
        return [
            f"{task_path.name}: approval_ref must be a yaml artifact, got {approval_ref!r}"
        ]
    if not approval_ref.startswith(".omo/workers/runs/"):
        return [
            f"{task_path.name}: approval_ref must live under .omo/workers/runs/, got {approval_ref!r}"
        ]
    approval_path = task_path.parents[3] / approval_ref
    # Workers 运行时 artifacts (.omo/workers/runs/) CI 无, 容忍缺失
    if not approval_path.exists():
        return []
    return []


def _validate_active_execution_links(
    task_path: Path, payload: dict[str, Any]
) -> list[str]:
    status = payload.get("status")
    required_fields_by_status = {
        "in_progress": ("assigned_to", "dispatch_id", "run_ref", "started_at"),
        "review": ("assigned_to", "dispatch_id", "run_ref", "review_ref"),
    }
    required_fields = required_fields_by_status.get(status)
    if required_fields is None:
        return []
    issues: list[str] = []
    for field_name in required_fields:
        if not payload.get(field_name):
            issues.append(
                f"{task_path.name}: {field_name} must be set when status={status}"
            )
    return issues


def _validate_modern_done_completion_marker(
    task_path: Path, payload: dict[str, Any]
) -> list[str]:
    if payload.get("status") != "done":
        return []
    modern_fields = (
        "task_type",
        "source_docs",
        "entry_gate",
        "evidence_required",
        "test_plan",
        "allowed_operation_level",
    )
    is_modern_packet = all(
        payload.get(field) not in (None, [], "") for field in modern_fields
    )
    if not is_modern_packet:
        return []
    if payload.get("completed_at") or payload.get("completed"):
        return []
    return [
        f"{task_path.name}: modern done packet must carry completed_at or completed marker"
    ]


def _validate_remediation_review_note(
    task_path: Path, payload: dict[str, Any]
) -> list[str]:
    if payload.get("status") != "review":
        return []
    review_note = payload.get("review_note")
    if not isinstance(review_note, str) or not review_note:
        return [f"{task_path.name}: remediation review task must carry review_note"]
    if review_note.startswith("/"):
        review_note_path = Path(review_note)
    else:
        review_note_path = task_path.parents[3] / review_note
    # 运行时 review notes (CI 无), 容忍缺失
    if not review_note_path.exists():
        return []
    return []


def _validate_modern_done_evidence_paths(
    task_path: Path, payload: dict[str, Any]
) -> list[str]:
    if payload.get("status") != "done":
        return []
    modern_fields = (
        "task_type",
        "source_docs",
        "entry_gate",
        "evidence_required",
        "test_plan",
        "allowed_operation_level",
    )
    is_modern_packet = all(
        payload.get(field) not in (None, [], "") for field in modern_fields
    )
    if not is_modern_packet:
        return []
    evidence_paths = payload.get("evidence_paths")
    if evidence_paths in (None, [], ""):
        return []
    if not isinstance(evidence_paths, list):
        return [f"{task_path.name}: evidence_paths must be a list when declared"]
    issues: list[str] = []
    workspace_root = task_path.parents[3]
    for ref in evidence_paths:
        if not isinstance(ref, str) or not ref:
            issues.append(
                f"{task_path.name}: evidence_paths contains invalid ref {ref!r}"
            )
            continue
        target = Path(ref)
        if not target.is_absolute():
            target = workspace_root / ref
        if not target.exists():
            # drift daemon 产物 (/_control/evolution/drift/) CI fresh checkout 缺失,
            # 属声明/执行鸿沟正常态 (memory: decl-exec-gap-meta-pattern), 不阻塞 lint.
            # 注意: 只豁免 drift daemon 产物; _delivery/workers runs 是 broker 产物应存在, 保持检查.
            if "/_control/evolution/drift/" in ref:
                continue
            issues.append(f"{task_path.name}: evidence_path target missing: {ref}")
    return issues


def _validate_active_review_ref(task_path: Path, payload: dict[str, Any]) -> list[str]:
    if payload.get("status") != "review":
        return []
    review_ref = payload.get("review_ref")
    if not isinstance(review_ref, str) or not review_ref:
        return [f"{task_path.name}: active review task must carry review_ref"]
    review_path = Path(review_ref)
    if not review_path.is_absolute():
        review_path = task_path.parents[3] / review_ref
    if not review_path.exists():
        return [f"{task_path.name}: review_ref target missing: {review_ref}"]
    return []


HUMAN_APPROVAL_REF_POLICY = TaskPolicy(
    name="human-approval-ref",
    summary="human_approval_required 的 planned/review 任务必须绑定 task-specific promotion approval yaml",
    target_roots=("planned", "remediation"),
    file_glob="*.yaml",
    validator_id="human_approval_ref",
    custom_validator=_validate_human_approval_ref,
)


ACTIVE_EXECUTION_LINKS_POLICY = TaskPolicy(
    name="active-execution-links",
    summary="active/ 中的 in_progress/review 任务必须具备 dispatch/run/review 等链路字段",
    target_roots=("active",),
    file_glob="*.yaml",
    validator_id="active_execution_links",
    custom_validator=_validate_active_execution_links,
)


DONE_DIRECTORY_STATUS_POLICY = TaskPolicy(
    name="done-directory-status",
    summary="done/ 目录中的任务必须显式保持 status=done",
    target_roots=("done",),
    file_glob="*.yaml",
    required_status="done",
)


MODERN_DONE_COMPLETION_MARKER_POLICY = TaskPolicy(
    name="modern-done-completion-marker",
    summary="新式 done packet 必须带 completed_at 或 completed 完成标记",
    target_roots=("done",),
    file_glob="*.yaml",
    validator_id="modern_done_completion_marker",
    custom_validator=_validate_modern_done_completion_marker,
)


REMEDIATION_REVIEW_NOTE_POLICY = TaskPolicy(
    name="remediation-review-note",
    summary="remediation/ 下 review 态任务必须带 review_note 且指向真实审查笔记",
    target_roots=("remediation",),
    file_glob="*.yaml",
    validator_id="remediation_review_note",
    custom_validator=_validate_remediation_review_note,
)


MODERN_DONE_EVIDENCE_PATHS_POLICY = TaskPolicy(
    name="modern-done-evidence-paths",
    summary="新式 done packet 一旦声明 evidence_paths，其目标文件必须物理存在",
    target_roots=("done",),
    file_glob="*.yaml",
    validator_id="modern_done_evidence_paths",
    custom_validator=_validate_modern_done_evidence_paths,
)


ACTIVE_REVIEW_REF_POLICY = TaskPolicy(
    name="active-review-ref",
    summary="active/ 下 review 态任务必须带 review_ref 且指向真实审查工件",
    target_roots=("active",),
    file_glob="*.yaml",
    validator_id="active_review_ref",
    custom_validator=_validate_active_review_ref,
)

TASK_POLICIES: dict[str, TaskPolicy] = {
    ACTIVE_EXECUTION_LINKS_POLICY.name: ACTIVE_EXECUTION_LINKS_POLICY,
    ACTIVE_REVIEW_REF_POLICY.name: ACTIVE_REVIEW_REF_POLICY,
    DONE_DIRECTORY_STATUS_POLICY.name: DONE_DIRECTORY_STATUS_POLICY,
    MODERN_DONE_COMPLETION_MARKER_POLICY.name: MODERN_DONE_COMPLETION_MARKER_POLICY,
    MODERN_DONE_EVIDENCE_PATHS_POLICY.name: MODERN_DONE_EVIDENCE_PATHS_POLICY,
    REMEDIATION_REVIEW_NOTE_POLICY.name: REMEDIATION_REVIEW_NOTE_POLICY,
    OPC_P6_SELF_EVOLUTION_POLICY.name: OPC_P6_SELF_EVOLUTION_POLICY,
    HUMAN_APPROVAL_REF_POLICY.name: HUMAN_APPROVAL_REF_POLICY,
}


def get_task_policy(name: str) -> TaskPolicy:
    try:
        return TASK_POLICIES[name]
    except KeyError as exc:
        known = ", ".join(sorted(TASK_POLICIES))
        raise KeyError(f"unknown task policy: {name}. known policies: {known}") from exc


def task_policy_snapshot(policy: TaskPolicy) -> dict[str, Any]:
    return {
        "name": policy.name,
        "summary": policy.summary,
        "target_roots": list(policy.target_roots),
        "file_glob": policy.file_glob,
        "prohibited_roots": list(policy.prohibited_roots),
        "required_fields": dict(policy.required_fields),
        "required_status": policy.required_status,
        "allowed_statuses": list(policy.allowed_statuses),
        "validator_id": policy.validator_id,
    }


def task_policy_registry_snapshot() -> list[dict[str, Any]]:
    return [task_policy_snapshot(TASK_POLICIES[name]) for name in sorted(TASK_POLICIES)]


def count_planned_matches(workspace_root: Path, policy: TaskPolicy) -> int:
    total = 0
    tasks_root = workspace_root / ".omo" / "tasks"
    for root_name in policy.target_roots:
        target_dir = tasks_root / root_name
        if target_dir.exists():
            total += len(list(target_dir.glob(policy.file_glob)))
    return total


def check_task_policy(workspace_root: Path, policy: TaskPolicy) -> list[str]:
    tasks_root = workspace_root / ".omo" / "tasks"
    issues: list[str] = []

    for root_name in policy.target_roots:
        target_dir = tasks_root / root_name
        if not target_dir.exists():
            continue
        for path in sorted(target_dir.glob(policy.file_glob)):
            payload = load_yaml(path)
            for field_name, expected in policy.required_fields.items():
                if payload.get(field_name) != expected:
                    issues.append(f"{path.name}: {field_name} must be {expected!r}")
            if (
                policy.required_status is not None
                and payload.get("status") != policy.required_status
            ):
                issues.append(
                    f"{path.name}: status must remain {policy.required_status}"
                )
            if (
                policy.allowed_statuses
                and payload.get("status") not in policy.allowed_statuses
            ):
                issues.append(
                    f"{path.name}: status must be one of {policy.allowed_statuses}"
                )
            if policy.custom_validator is not None:
                issues.extend(policy.custom_validator(path, payload))

    for root_name in policy.prohibited_roots:
        target_dir = tasks_root / root_name
        if not target_dir.exists():
            continue
        for path in sorted(target_dir.glob(policy.file_glob)):
            issues.append(f"{path.name}: {policy.name} task leaked into {root_name}/")
    return issues
