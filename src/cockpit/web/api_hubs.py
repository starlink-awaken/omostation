"""Read-only aggregation endpoints for Cockpit's research and protocol workbenches."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException

from cockpit.storage import get_data_access

router = APIRouter()


def _iso_timestamp(value: Any) -> str | None:
    if value is None:
        return None
    try:
        return datetime.fromtimestamp(float(value), tz=UTC).isoformat().replace("+00:00", "Z")
    except (TypeError, ValueError, OverflowError, OSError):
        return str(value)


def _safe_call(function: Callable[[], Any], default: Any) -> Any:
    try:
        return function()
    except Exception:
        return default


def _research_status(record: dict[str, Any]) -> str:
    if record.get("quarantined_at"):
        return "quarantined"
    if record.get("archived_at"):
        return "archived"
    return "active"


def build_research_hub() -> dict[str, Any]:
    """Aggregate the existing research SQLite records without introducing a second store."""
    access = get_data_access()
    records = _safe_call(
        lambda: access.list_research(limit=1000, include_quarantined=True, include_archived=True),
        [],
    )
    records = records if isinstance(records, list) else []

    recent: list[dict[str, Any]] = []
    published_count = 0
    follow_up_count = 0
    agents: set[str] = set()

    for record in records[:20]:
        if not isinstance(record, dict):
            continue
        research_id = record.get("id")
        full_record = _safe_call(lambda: access.get_research(int(research_id)), record) if research_id is not None else record
        full_record = full_record if isinstance(full_record, dict) else record
        follow_ups = full_record.get("follow_ups") or []
        follow_up_count += len(follow_ups) if isinstance(follow_ups, list) else 0
        agent = str(full_record.get("agent") or record.get("agent") or "").strip()
        if agent:
            agents.add(agent)

        dossier = _safe_call(
            lambda: access.get_research_dossier(int(research_id)),
            {},
        ) if research_id is not None else {}
        dossier = dossier if isinstance(dossier, dict) else {}
        publications = dossier.get("publications") or []
        if publications:
            published_count += 1

        timeline = _safe_call(
            lambda: access.get_research_timeline(int(research_id)),
            [],
        ) if research_id is not None else []
        timeline = timeline if isinstance(timeline, list) else []
        last_event = max(
            (event for event in timeline if isinstance(event, dict)),
            key=lambda event: float(event.get("created_at") or 0),
            default=None,
        )
        status = _research_status(record)
        if publications:
            next_action = f"继续打开研究或处理追问：cockpit research --open {research_id}"
        else:
            next_action = f"发布一版研究摘要：cockpit research --publish {research_id} --style brief"

        recent.append(
            {
                "id": research_id,
                "topic": record.get("topic") or "未命名研究",
                "summary": record.get("summary") or "",
                "created_at": _iso_timestamp(record.get("created_at")),
                "source_count": int(record.get("source_count") or 0),
                "tags": record.get("tags") or [],
                "agent": agent or None,
                "status": status,
                "follow_up_count": len(follow_ups) if isinstance(follow_ups, list) else 0,
                "last_event": {
                    "type": last_event.get("event_type"),
                    "label": last_event.get("event_type"),
                    "created_at": _iso_timestamp(last_event.get("created_at")),
                    "description": last_event.get("description"),
                } if last_event else None,
                "next_action": next_action,
            }
        )

    active_count = sum(1 for record in records if _research_status(record) == "active")
    archived_count = sum(1 for record in records if _research_status(record) == "archived")
    quarantined_count = sum(1 for record in records if _research_status(record) == "quarantined")
    latest_id = recent[0]["id"] if recent else None

    return {
        "status": "ok",
        "summary": {
            "total": len(records),
            "active": active_count,
            "archived": archived_count,
            "quarantined": quarantined_count,
            "published": published_count,
            "follow_ups": follow_up_count,
            "agents": len(agents),
        },
        "recent": recent,
        "commands": [
            {
                "id": "research-start",
                "label": "发起新研究",
                "value": 'cockpit research "你的研究主题"',
                "detail": "从一个明确问题开始，结果会进入 Cockpit 研究 SQLite。",
            },
            {
                "id": "research-publish",
                "label": "发布最近研究",
                "value": f"cockpit research --publish {latest_id} --style brief" if latest_id else 'cockpit research --publish <ID> --style brief',
                "detail": "把研究对象转成可追踪的报告输出。",
            },
            {
                "id": "research-daily",
                "label": "生成研究简报",
                "value": "cockpit daily",
                "detail": "汇总研究对象、追问和下一步动作。",
            },
        ],
        "pipeline": [
            {"id": "research", "title": "研究", "summary": "建立问题、来源和研究对象。"},
            {"id": "follow-up", "title": "追问", "summary": "补上下文，减少研究结果闲置。"},
            {"id": "publish", "title": "发布", "summary": "把研究转成报告或长期知识资产。"},
            {"id": "task", "title": "承接", "summary": "把结论带回任务中心和治理路径。"},
        ],
        "related_pages": [
            {"id": "Knowledge", "title": "知识中枢", "reason": "沉淀研究结论和长期上下文。"},
            {"id": "Assets", "title": "技术资产库", "reason": "确认研究所需的技能和工作流资产。"},
            {"id": "TaskCenter", "title": "任务中心", "reason": "承接研究后的下一步动作。"},
        ],
    }


def build_research_detail(research_id: int) -> dict[str, Any]:
    """Return one research object with its existing evidence and relations."""
    access = get_data_access()
    record = _safe_call(lambda: access.get_research(research_id), None)
    if not isinstance(record, dict):
        return {"status": "not_found", "research_id": research_id}

    dossier = _safe_call(lambda: access.get_research_dossier(research_id), {})
    dossier = dossier if isinstance(dossier, dict) else {}
    timeline = _safe_call(lambda: access.get_research_timeline(research_id), [])
    timeline = timeline if isinstance(timeline, list) else []
    normalized_timeline = [
        {
            **event,
            "created_at": _iso_timestamp(event.get("created_at")),
        }
        for event in timeline
        if isinstance(event, dict)
    ]
    normalized_dossier = {
        "parents": dossier.get("parents") or [],
        "children": dossier.get("children") or [],
        "publications": [
            {
                **publication,
                "published_at": _iso_timestamp(publication.get("published_at")),
            }
            for publication in dossier.get("publications") or []
            if isinstance(publication, dict)
        ],
    }

    return {
        "status": "ok",
        "item": {
            "id": research_id,
            "topic": record.get("topic") or "未命名研究",
            "summary": record.get("summary") or "",
            "full_text": record.get("full_text") or "",
            "created_at": _iso_timestamp(record.get("created_at")),
            "source_count": int(record.get("source_count") or 0),
            "tags": record.get("tags") or [],
            "follow_ups": record.get("follow_ups") or [],
            "agent": record.get("agent") or None,
            "status": _research_status(record),
        },
        "timeline": normalized_timeline,
        "dossier": normalized_dossier,
        "half_life": _safe_call(lambda: access.compute_half_life(research_id), {}),
    }


def _safe_registry(function: Callable[[], Any]) -> list[dict[str, Any]]:
    value = _safe_call(function, [])
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def build_protocol_hub() -> dict[str, Any]:
    """Aggregate eCOS registries and recent runs for the protocol workbench."""
    try:
        from cockpit.adapters.ecos import list_actions, list_backends, list_workflows, load_all_workflow_runs

        workflows = _safe_registry(list_workflows)
        actions = _safe_registry(list_actions)
        backends = _safe_registry(list_backends)
        runs = _safe_registry(load_all_workflow_runs)
    except Exception:
        workflows, actions, backends, runs = [], [], [], []

    layers = [
        {
            "id": "ecos-workflows",
            "title": "eCOS 工作流定义",
            "status": "ready" if workflows else "watch",
            "role": "协议层的可执行工作流注册表",
            "facts": [f"已注册 {len(workflows)} 条工作流"],
            "next_action": "进入资产库查看定义，或用工作流验证接口确认约束。",
        },
        {
            "id": "ecos-actions",
            "title": "Workflow Actions",
            "status": "ready" if actions else "watch",
            "role": "工作流可以调用的动作能力",
            "facts": [f"已注册 {len(actions)} 个动作"],
            "next_action": "检查动作是否有明确 backend、权限和证据输出。",
        },
        {
            "id": "ecos-backends",
            "title": "Workflow Backends",
            "status": "ready" if backends else "watch",
            "role": "工作流动作的执行后端",
            "facts": [f"已注册 {len(backends)} 个后端"],
            "next_action": "检查后端健康和最近运行记录。",
        },
    ]
    ready_layers = sum(1 for layer in layers if layer["status"] == "ready")

    return {
        "status": "ok",
        "summary": {
            "workflow_definitions": len(workflows),
            "workflow_actions": len(actions),
            "workflow_backends": len(backends),
            "recent_runs": len(runs[:20]),
            "ready_layers": ready_layers,
            "watch_layers": len(layers) - ready_layers,
            "page_score": round(ready_layers / len(layers) * 100) if layers else 0,
        },
        "layers": layers,
        "recent_workflows": runs[:20],
        "commands": [
            {
                "id": "protocol-status",
                "label": "查看协议状态",
                "value": "cockpit status",
                "detail": "读取 Cockpit、研究和协议层的统一状态。",
            },
            {
                "id": "workflow-list",
                "label": "列出工作流",
                "value": "cockpit workflow --list",
                "detail": "确认注册表中的工作流定义和执行入口。",
            },
            {
                "id": "workflow-audit",
                "label": "验证工作流",
                "value": "uv run --project projects/cockpit pytest src/cockpit/tests/test_status_render_workbench.py -q",
                "detail": "用项目测试验证协议工作台和状态聚合。",
            },
        ],
        "related_pages": [
            {"id": "Assets", "title": "技术资产库", "reason": "查看工作流、技能和管线定义。"},
            {"id": "Workflows", "title": "工作流", "reason": "查看运行记录和人工审批节点。"},
            {"id": "C2G", "title": "C2G 战略中心", "reason": "把协议缺口沉到治理动作。"},
        ],
        "roadmap_item": {
            "id": "protocol-hub-runtime",
            "title": "协议工作台运行状态接入",
            "priority": "P1",
            "problem": "协议页面需要同时看定义、动作、后端和运行证据。",
        },
        "playbook": {
            "id": "protocol-integrity-check",
            "title": "协议层完整性检查",
            "goal": "巡检工作流定义、动作注册、后端和最近运行证据。",
        },
    }


@router.get("/api/cockpit/research-hub")
async def get_research_hub() -> dict[str, Any]:
    return build_research_hub()


@router.get("/api/cockpit/research-hub/{research_id}")
async def get_research_detail(research_id: int) -> dict[str, Any]:
    payload = build_research_detail(research_id)
    if payload.get("status") == "not_found":
        raise HTTPException(status_code=404, detail="research object not found")
    return payload


@router.get("/api/cockpit/protocol-hub")
async def get_protocol_hub() -> dict[str, Any]:
    return build_protocol_hub()
