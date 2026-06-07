"""Swarm MCP Tools — 蜂群状态查询与节点管理"""
from __future__ import annotations

from fastmcp import FastMCP


def register_swarm_tools(mcp: FastMCP) -> None:
    """注册蜂群相关 MCP 工具。"""

    @mcp.tool()
    async def swarm_status() -> dict:
        """查询蜂群状态: 节点列表、角色分布、在线状态。"""
        try:
            from agora.mcp.swarm import get_swarm
            swarm = get_swarm()
            return swarm.status()
        except Exception as e:
            return {"status": "error", "error": str(e)}

    @mcp.tool()
    async def swarm_nodes(role: str = "") -> dict:
        """列出蜂群中的节点。

        Args:
            role: 过滤角色 (master/worker/function)
        """
        try:
            from agora.mcp.swarm import get_swarm
            swarm = get_swarm()
            nodes = swarm.get_online_nodes(role=role)
            return {
                "total": len(nodes),
                "nodes": [n.to_dict() for n in nodes],
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    @mcp.tool()
    async def swarm_resolve(uri: str) -> dict:
        """在蜂群中查找能处理指定 BOS URI 的节点。

        Args:
            uri: BOS URI (e.g. bos://memory/kos/search)
        """
        try:
            from agora.mcp.swarm import get_swarm
            swarm = get_swarm()
            node = swarm.get_node_by_uri(uri)
            if node:
                return {"found": True, "node": node.to_dict()}
            return {"found": False, "uri": uri, "hint": "No online node can handle this URI"}
        except Exception as e:
            return {"status": "error", "error": str(e)}
