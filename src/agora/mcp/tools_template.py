"""MCP Tool 开发模板 — Agora MCP Server。

所有 @mcp.tool() 函数必须遵守以下契约：
  1. 返回类型为 dict（由 fastmcp 自动序列化为 JSON）
  2. 返回值必须包含 "format_version" 字段
  3. 遵循 _ok() / _error() 辅助函数模式

Extracted from SharedBrain D_Gateway.
"""

from __future__ import annotations

from fastmcp import FastMCP

# ── MCP 实例 ─────────────────────────────────────────
mcp = FastMCP("agora-agent-router-template")


# ── 常量 ─────────────────────────────────────────────
FORMAT_VERSION = "agora-v1"


# ── 辅助函数 ─────────────────────────────────────────
# _ok() / _error() 集中管理返回格式。
# 注意：_ok() 的 data 参数中不内建 format_version，
# 要求每个工具函数显式传递（以便 SOP 的 AST 静态检测能在工具函数体中找到字面量）。


def _error(msg: str) -> dict:
    """返回标准错误响应（内建 format_version，工具函数无需额外传入）。"""
    return {"status": "error", "error": msg, "format_version": FORMAT_VERSION}


def _ok(data: dict) -> dict:
    """返回标准成功响应。data 中应包含 format_version 字段。"""
    return {"status": "ok", **data}


# ── 工具函数示例 ─────────────────────────────────────
# Agora 工具模式说明：
#   1. 全部同步函数，直接 @mcp.tool() 装饰
#   2. 返回格式统一：dict 中直接内联 format_version
#   3. 使用 try/except 包装异常路径
#   4. 工具名简短（agent_send, workflow_status 等）
#
# 模板工具建议逐步迁移到 _ok() 模式。


@mcp.tool()
def sample_send_message(source: str, target: str, content: str) -> dict:
    """在 Agent 之间发送消息（示例）。

    Args:
        source: 发送方 Agent 名称
        target: 接收方 Agent 名称
        content: 消息内容
    """
    try:
        msg_id = f"msg_{__import__('uuid').uuid4().hex[:8]}"

        return _ok(
            {
                "format_version": FORMAT_VERSION,
                "message_id": msg_id,
                "status": "routed",
                "source": source,
                "target": target,
            }
        )
    except Exception as e:
        return _error(str(e))


@mcp.tool()
def sample_query_status() -> dict:
    """查询当前系统状态（示例）。"""
    try:
        return _ok(
            {
                "format_version": FORMAT_VERSION,
                "pending": {"agent_a": 3, "agent_b": 1},
                "recently_completed": [],
            }
        )
    except Exception as e:
        return _error(str(e))


@mcp.tool()
def sample_threat_assessment(source_id: str) -> dict:
    """对指定来源进行威胁评估（示例）。"""
    try:
        return _ok(
            {
                "format_version": FORMAT_VERSION,
                "source_id": source_id,
                "threat_score": 0,
                "risk_level": "low",
                "details": {},
            }
        )
    except Exception as e:
        return _error(str(e))


def main() -> None:
    """运行 MCP server（stdio 模式）。"""
    mcp.run()


if __name__ == "__main__":
    main()
