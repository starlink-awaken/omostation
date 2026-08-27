"""MCP Tool 开发模板 — Iris 连接器中枢。

所有 @mcp.tool() 函数必须遵守以下契约：
  1. 返回类型为 dict（由 fastmcp 自动序列化为 JSON）
  2. 返回值必须包含 "format_version" 字段
  3. 遵循 _ok() / _error() 辅助函数模式

上下文：iris/src/iris/mcp_server.py
"""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

# ── MCP 实例 ─────────────────────────────────────────
mcp = FastMCP(
    "iris-mcp-tools v1.0 — 连接器中枢工具模板",
    mask_error_details=True,
)


# ── 常量 ─────────────────────────────────────────────
FORMAT_VERSION = "iris-v1"


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
# Iris 工具模式说明：
#   1. 同步函数直接 return
#   2. 成功路径：return {"items": items, "format_version": FORMAT_VERSION}
#   3. 错误路径：return {"error": msg, "format_version": FORMAT_VERSION}
#   4. 文档字符串包含 Args: 描述参数
#
# Iris 当前风格：大部分工具返回 list（items），顶部由 _ensure_registry() / _ensure_eidos() 惰性初始化。
# 模板工具兼容并建议逐步迁移到 _ok() 模式。


@mcp.tool()
def sample_list_connectors() -> dict[str, Any]:
    """列举所有已注册的连接器（示例 — 适配 Iris 实际模式）。

    Args:
        无参数

    Returns:
        包含 items 列表和 format_version 的 dict。
    """
    try:
        # ── 模拟：实际调用 registry.status_all() ──
        connectors = [
            {"name": "obsidian", "available": True},
            {"name": "wps_note", "available": False},
        ]

        return _ok(
            {
                "format_version": FORMAT_VERSION,
                "items": connectors,
                "total": len(connectors),
            }
        )
    except Exception as e:
        return _error(str(e))


@mcp.tool()
def sample_get_item(platform: str, item_id: str) -> dict[str, Any]:
    """获取指定平台上的单个条目（示例）。

    Args:
        platform: 平台名称（如 obsidian, wps_note）
        item_id: 条目 ID
    """
    try:
        # ── 模拟：实际调用 conn.get_item(id) ──
        item = {"id": item_id, "title": "Sample Item"}

        return _ok(
            {
                "format_version": FORMAT_VERSION,
                "item": item,
            }
        )
    except Exception as e:
        return _error(str(e))


@mcp.tool()
def sample_validate(
    data: dict[str, Any],
    schema_type: str = "KnowledgeCard",
) -> dict[str, Any]:
    """验证字典是否符合指定 Schema（示例）。

    Args:
        data: 要验证的数据
        schema_type: Schema 类型（KnowledgeCard / Fact / OntologyNode）
    """
    try:
        # ── 模拟：实际调用 eidos.validate_knowledge_card(data) ──
        validation_result = {"is_valid": True, "errors": []}

        return _ok(
            {
                "format_version": FORMAT_VERSION,
                "is_valid": validation_result["is_valid"],
                "errors": validation_result.get("errors", []),
            }
        )
    except Exception as e:
        return _error(str(e))


# ── 入口点 ──────────────────────────────────────────


def main() -> None:
    """运行 MCP server（stdio 模式，供 Agora 集成）。"""
    from iris.mcp_server import main as iris_main

    iris_main()


if __name__ == "__main__":
    main()
