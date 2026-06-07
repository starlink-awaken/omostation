"""AetherForge 统一 MCP Server — 整合 gateway + mesh 的所有 MCP tools。

启动方式:
    aetherforge-mcp

暴露工具:
    forge_generate        → gateway LLM 生成
    forge_list_nodes      → mesh 节点列表
    forge_mesh_status     → mesh 健康状态
    forge_health_check    → mesh 批量健康检查
    forge_cost_report     → mesh 成本报告
"""

from __future__ import annotations

from fastmcp import FastMCP

from compute_mesh.api.mcp_server import (
    mesh_cost_report,
    mesh_generate,
    mesh_health_check,
    mesh_list_nodes,
    mesh_status,
)
from llm_gateway.mcp_server import llm_generate

mcp = FastMCP("aetherforge")


# ── Gateway tools ──────────────────────────────────────────────────────────
mcp.tool(name="forge_generate")(llm_generate)

# ── Mesh tools ─────────────────────────────────────────────────────────────
mcp.tool(name="forge_list_nodes")(mesh_list_nodes)
mcp.tool(name="forge_mesh_status")(mesh_status)
mcp.tool(name="forge_health_check")(mesh_health_check)
mcp.tool(name="forge_cost_report")(mesh_cost_report)
mcp.tool(name="forge_generate_mesh")(mesh_generate)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
