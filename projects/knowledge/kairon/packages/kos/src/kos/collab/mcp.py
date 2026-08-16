"""KOS Collab MCP — L3协作层MCP工具导出。

导出: COLLAB_TOOLS (工具定义), COLLAB_HANDLERS (handler函数)
"""

from typing import Any

from kos.collab.api import (  # type: ignore[import-not-found]
    add_artifact,
    claim_subtask,
    complete_subtask,
    create_task,
    get_task,
    list_tasks,
    update_task,
)

COLLAB_TOOLS: dict[str, dict[str, Any]] = {
    "collab.create_task": {
        "description": "创建协作任务。返回任务对象含task_id。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "任务标题"},
                "goal": {"type": "string", "description": "任务目标"},
                "creator": {"type": "string", "description": "创建者标识"},
                "visibility_scope": {
                    "type": "string",
                    "enum": ["private", "team", "org", "public"],
                    "description": "可见范围",
                },
                "subtasks": {
                    "type": "array",
                    "items": {"type": "object"},
                    "description": "子任务列表",
                },
            },
            "required": ["title", "goal", "creator"],
        },
    },
    "collab.get_task": {
        "description": "按task_id获取任务详情，含子任务和产出物。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "string", "description": "任务ID"},
            },
            "required": ["task_id"],
        },
    },
    "collab.list_tasks": {
        "description": "列出任务列表，可按status/creator过滤。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "status": {"type": "string", "description": "按状态过滤"},
                "creator": {"type": "string", "description": "按创建者过滤"},
                "limit": {"type": "integer", "description": "最大返回数", "default": 20},
            },
            "required": [],
        },
    },
    "collab.update_task": {
        "description": "更新任务字段：title/goal/visibility_scope/status/resource_usage。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "string", "description": "任务ID"},
                "data": {"type": "object", "description": "要更新的字段"},
            },
            "required": ["task_id", "data"],
        },
    },
    "collab.claim_subtask": {
        "description": "认领子任务。含BEGIN IMMEDIATE行锁+依赖检查。依赖未满足→DEPENDENCY_NOT_MET。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "string", "description": "任务ID"},
                "subtask_index": {"type": "integer", "description": "子任务索引(从0开始)"},
                "assignee": {"type": "string", "description": "认领者标识"},
            },
            "required": ["task_id", "subtask_index", "assignee"],
        },
    },
    "collab.add_artifact": {
        "description": "给任务添加产出物（文件、报告等）。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "string", "description": "任务ID"},
                "artifact": {
                    "type": "object",
                    "description": "产出物对象 {id, type, uri, description}",
                },
            },
            "required": ["task_id", "artifact"],
        },
    },
    "collab.update_visibility": {
        "description": "修改Task的可见范围 (private/team/org/public)。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task_id": {"type": "string", "description": "任务ID"},
                "visibility_scope": {
                    "type": "string",
                    "enum": ["private", "team", "org", "public"],
                    "description": "可见范围",
                },
            },
            "required": ["task_id", "visibility_scope"],
        },
    },
}


def _handle_create_task(args: dict[str, Any]) -> dict[str, Any]:
    try:
        t = create_task(
            title=args["title"],
            goal=args["goal"],
            creator=args["creator"],
            visibility_scope=args.get("visibility_scope", "private"),
            subtasks=args.get("subtasks"),
        )
        return {"status": "created", "task": t}
    except Exception as e:
        return {"error": str(e), "code": "INTERNAL_ERROR"}


def _handle_get_task(args: dict[str, Any]) -> dict[str, Any]:
    try:
        t = get_task(args["task_id"])
        if t is None:
            return {"error": f"Task not found: {args['task_id']}", "code": "NOT_FOUND"}
        return {"status": "ok", "task": t}
    except Exception as e:
        return {"error": str(e), "code": "INTERNAL_ERROR"}


def _handle_list_tasks(args: dict[str, Any]) -> dict[str, Any]:
    try:
        tasks = list_tasks(
            status=args.get("status", ""),
            creator=args.get("creator", ""),
            limit=args.get("limit", 20),
        )
        return {"status": "ok", "tasks": tasks, "count": len(tasks)}
    except Exception as e:
        return {"error": str(e), "code": "INTERNAL_ERROR"}


def _handle_update_task(args: dict[str, Any]) -> dict[str, Any]:
    try:
        t = update_task(args["task_id"], args["data"])
        if t is None:
            return {"error": f"Task not found: {args['task_id']}", "code": "NOT_FOUND"}
        return {"status": "updated", "task": t}
    except Exception as e:
        return {"error": str(e), "code": "INTERNAL_ERROR"}


def _handle_claim_subtask(args: dict[str, Any]) -> dict[str, Any]:
    try:
        return claim_subtask(
            task_id=args["task_id"],
            subtask_index=int(args["subtask_index"]),
            assignee=args["assignee"],
        )
    except Exception as e:
        return {"error": str(e), "code": "INTERNAL_ERROR"}


def _handle_complete_subtask(args: dict[str, Any]) -> dict[str, Any]:
    try:
        return complete_subtask(
            task_id=args["task_id"],
            subtask_index=int(args.get("subtask_index", 0)),
            assignee=args.get("assignee", ""),
        )
    except Exception as e:
        return {"error": str(e), "code": "INTERNAL_ERROR"}


def _handle_add_artifact(args: dict[str, Any]) -> dict[str, Any]:
    try:
        t = add_artifact(args["task_id"], args["artifact"])
        if t is None:
            return {"error": f"Task not found: {args['task_id']}", "code": "NOT_FOUND"}
        return {"status": "artifact_added", "task": t}
    except Exception as e:
        return {"error": str(e), "code": "INTERNAL_ERROR"}


def _handle_update_visibility(args: dict[str, Any]) -> dict[str, Any]:
    try:
        from kos.collab.api import update_task

        t = update_task(args["task_id"], {"visibility_scope": args["visibility_scope"]})
        if t is None:
            return {"error": f"Task not found: {args['task_id']}", "code": "NOT_FOUND"}
        return {"status": "visibility_updated", "task": t}
    except Exception as e:
        return {"error": str(e), "code": "INTERNAL_ERROR"}


COLLAB_HANDLERS: dict[str, Any] = {
    "collab.create_task": _handle_create_task,
    "collab.get_task": _handle_get_task,
    "collab.list_tasks": _handle_list_tasks,
    "collab.update_task": _handle_update_task,
    "collab.claim_subtask": _handle_claim_subtask,
    "collab.add_artifact": _handle_add_artifact,
    "collab.update_visibility": _handle_update_visibility,
}
