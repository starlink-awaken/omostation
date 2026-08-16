"""KOS Consensus MCP — X3价值堆栈MCP工具导出。

导出: CONSENSUS_TOOLS (工具定义), CONSENSUS_HANDLERS (handler函数)
"""

from typing import Any

from kos.consensus.api import (  # type: ignore[import-not-found]
    create_consensus,
    get_consensus,
    get_entity_consensus,
    list_expired_consensus,
    mark_expired,
    renew_consensus,
    trace_consensus,
)

CONSENSUS_TOOLS: dict[str, dict[str, Any]] = {
    "consensus.create": {
        "description": "创建三级共识(L1 Agent自检/L2 User确认/L3 RedTeam验证)。有效期: L1=30天, L2=90天, L3=365天。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "entity_id": {"type": "string", "description": "关联实体ID"},
                "agreed_by": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "共识参与方 (user:xxx→L2, redteam:xxx→L3, 否则L1)",
                },
                "agreement": {"type": "string", "description": "共识内容"},
                "source_session": {"type": "string", "description": "来源会话ID"},
                "provenance_chain": {
                    "type": "array",
                    "items": {"type": "object"},
                    "description": "引用链追溯 — 每步含 source/timestamp/action",
                },
            },
            "required": ["entity_id", "agreed_by", "agreement"],
        },
    },
    "consensus.get": {
        "description": "获取共识详情或某实体的活跃共识列表。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "consensus_id": {"type": "string", "description": "共识ID (直接查询)"},
                "entity_id": {"type": "string", "description": "实体ID (列出活跃共识)"},
            },
            "required": [],
        },
    },
    "consensus.list_expired": {
        "description": "列出已过期但未标记的共识。用于保鲜巡检。",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    "consensus.renew": {
        "description": "续签共识。L1自动续签无需参数；L2/L3需提供新的agreed_by。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "consensus_id": {"type": "string", "description": "共识ID"},
                "agreed_by": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "续签参与方 (L2/L3必需)",
                },
            },
            "required": ["consensus_id"],
        },
    },
    "consensus.trace": {
        "description": "追踪共识的完整引用链。返回实体活跃共识及每条共识的 provenance_chain 执行链。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "entity_id": {"type": "string", "description": "实体ID"},
            },
            "required": ["entity_id"],
        },
    },
}


def _handle_create(args: dict[str, Any]) -> dict[str, Any]:
    try:
        c = create_consensus(
            entity_id=args["entity_id"],
            agreed_by=args["agreed_by"],
            agreement=args["agreement"],
            source_session=args.get("source_session", ""),
            provenance_chain=args.get("provenance_chain"),
        )
        return {"status": "created", "consensus": c}
    except Exception as e:
        return {"error": str(e), "code": "INTERNAL_ERROR"}


def _handle_get(args: dict[str, Any]) -> dict[str, Any]:
    try:
        cid = args.get("consensus_id", "")
        eid = args.get("entity_id", "")
        if cid:
            c = get_consensus(cid)
            if c is None:
                return {"error": f"Consensus not found: {cid}", "code": "NOT_FOUND"}
            return {"status": "ok", "consensus": c}
        if eid:
            cons = get_entity_consensus(eid)
            return {"status": "ok", "consensus_list": cons, "count": len(cons)}
        return {"error": "Provide consensus_id or entity_id", "code": "INVALID_PARAM"}
    except Exception as e:
        return {"error": str(e), "code": "INTERNAL_ERROR"}


def _handle_list_expired(_args: dict[str, Any]) -> dict[str, Any]:
    try:
        mark_expired()
        expired = list_expired_consensus()
        return {"status": "ok", "expired": expired, "count": len(expired)}
    except Exception as e:
        return {"error": str(e), "code": "INTERNAL_ERROR"}


def _handle_renew(args: dict[str, Any]) -> dict[str, Any]:
    try:
        return renew_consensus(
            consensus_id=args["consensus_id"],
            agreed_by=args.get("agreed_by"),
        )
    except Exception as e:
        return {"error": str(e), "code": "INTERNAL_ERROR"}


def _handle_trace(args: dict[str, Any]) -> dict[str, Any]:
    try:
        return trace_consensus(entity_id=args["entity_id"])
    except Exception as e:
        return {"error": str(e), "code": "INTERNAL_ERROR"}


CONSENSUS_HANDLERS: dict[str, Any] = {
    "consensus.create": _handle_create,
    "consensus.get": _handle_get,
    "consensus.list_expired": _handle_list_expired,
    "consensus.renew": _handle_renew,
    "consensus.trace": _handle_trace,
}
