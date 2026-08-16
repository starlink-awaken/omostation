"""KOS Self MCP — L4自我层MCP工具导出。

导出: SELF_TOOLS (工具定义), SELF_HANDLERS (handler函数)
每个handler返回dict，不raise。
"""

from typing import Any

from kos.self.api import (  # type: ignore[import-not-found]
    get_current_role,
    get_profile,
    get_vision_summary,
    skill_router,
)

SELF_TOOLS: dict[str, dict[str, Any]] = {
    "self.get_profile": {
        "description": "获取当前用户的完整画像：身份、角色、愿景、原则、认知框架。用于Agent理解用户上下文。",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    "self.get_current_role": {
        "description": "按当前时间和时间窗口判断活跃角色。工作日白天→工作角色，晚上/周末→个人/家庭角色。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "context_hint": {
                    "type": "string",
                    "description": "上下文提示，用于匹配特定角色标签或名称",
                },
            },
            "required": [],
        },
    },
    "self.get_vision_summary": {
        "description": "获取L4自我层上下文摘要：当前角色+愿景+核心原则+认知框架+OKR进度。用于Agent prompt注入。",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    "kos_skill_router": {
        "description": "根据当前角色、任务描述与历史反馈，推荐、登记或回写 skill 路由结果。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "route / feedback / register",
                },
                "task_description": {
                    "type": "string",
                    "description": "当前任务描述，用于 route 匹配",
                },
                "context_hint": {
                    "type": "string",
                    "description": "角色提示，如 家庭/架构/研究",
                },
                "available_skills": {
                    "type": "array",
                    "description": "可选 skill 列表",
                    "items": {"type": "object"},
                },
                "available_tools": {
                    "type": "array",
                    "description": "当前可用工具标签",
                    "items": {"type": "string"},
                },
                "limit": {
                    "type": "number",
                    "description": "返回的推荐数量",
                    "default": 5,
                },
                "skill_definition": {
                    "type": "object",
                    "description": "register 动作的 skill 定义",
                },
                "skill_name": {
                    "type": "string",
                    "description": "feedback 动作的 skill 名称",
                },
                "accepted": {
                    "type": "boolean",
                    "description": "feedback 是否采纳",
                    "default": True,
                },
                "reason": {
                    "type": "string",
                    "description": "feedback 原因",
                },
            },
            "required": ["action"],
        },
    },
}


def _handle_get_profile() -> dict[str, Any]:
    try:
        return get_profile()
    except Exception as e:
        return {"error": str(e)}


def _handle_get_current_role(args: dict[str, Any]) -> dict[str, Any]:
    try:
        return get_current_role(context_hint=args.get("context_hint", ""))
    except Exception as e:
        return {"error": str(e)}


def _handle_get_vision_summary() -> dict[str, Any]:
    try:
        summary = get_vision_summary()
        return {"summary": summary}
    except Exception as e:
        return {"error": str(e)}


def _handle_skill_router(args: dict[str, Any]) -> dict[str, Any]:
    try:
        return skill_router(
            action=str(args.get("action", "route")),
            task_description=str(args.get("task_description", "")),
            context_hint=str(args.get("context_hint", "")),
            available_skills=args.get("available_skills") or [],
            available_tools=args.get("available_tools") or [],
            limit=int(args.get("limit", 5)),
            skill_definition=args.get("skill_definition") or {},
            skill_name=str(args.get("skill_name", "")),
            accepted=bool(args.get("accepted", True)),
            reason=str(args.get("reason", "")),
        )
    except Exception as e:
        return {"error": str(e)}


SELF_HANDLERS: dict[str, Any] = {
    "self.get_profile": _handle_get_profile,
    "self.get_current_role": lambda args=None: _handle_get_current_role(args or {}),
    "self.get_vision_summary": _handle_get_vision_summary,
    "kos_skill_router": lambda args=None: _handle_skill_router(args or {}),
}
