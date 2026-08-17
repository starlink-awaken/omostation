"""MCP Tool 开发模板 — 标准返回契约。

所有 @mcp.tool() 函数必须遵守以下契约：
  1. 返回类型为 dict（由 fastmcp 自动序列化为 JSON）
  2. 返回值必须包含 "format_version" 字段
  3. 遵循 _ok() / _error() 辅助函数模式

上下文：AGENTS.md 项目治理规范
"""

from __future__ import annotations

from fastmcp import FastMCP

# ── MCP 实例 ─────────────────────────────────────────
mcp = FastMCP(
    "my-project-name v1.0 — Description",
    mask_error_details=True,
)


# ── 常量 ─────────────────────────────────────────────
# 命名规范："{project_name}-v{major}"，如 myproject-v1
FORMAT_VERSION = "myproject-v1"


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
# 所有 @mcp.tool() 必须遵循：
#   1. 同步函数直接 return，异步用 async/await
#   2. 成功路径：return _ok({"format_version": FORMAT_VERSION, ...})
#   3. 错误路径：return _error(str(e))
#   4. 文档字符串包含 Args: 描述参数


@mcp.tool()
def sample_sync_tool(name: str = "default") -> dict:
    """示例同步工具。

    Args:
        name: 名称参数
    """
    try:
        # ── 核心逻辑 ──
        result = {"greeting": f"Hello, {name}!"}

        return _ok(
            {
                "format_version": FORMAT_VERSION,
                **result,
            }
        )
    except Exception as e:
        return _error(str(e))


@mcp.tool()
async def sample_async_tool(query: str, limit: int = 10) -> dict:
    """示例异步工具。

    Args:
        query: 搜索关键词
        limit: 返回结果上限
    """
    try:
        # ── 模拟异步调用 ──
        items = await _fetch_some_data(query, limit)

        return _ok(
            {
                "format_version": FORMAT_VERSION,
                "query": query,
                "count": len(items),
                "items": items,
            }
        )
    except Exception as e:
        return _error(str(e))


# ── 边界情况示例 ──────────────────────────────────────


@mcp.tool()
def sample_item_detail(item_id: str) -> dict:
    """返回单个条目（非列表），展示 dict 内 format_version 注入。"""
    try:
        item = {"id": item_id, "value": 42}

        # 方式 A：在 _ok() 参数中包含（推荐 — AST 可静态检测）
        result = _ok({"format_version": FORMAT_VERSION, **item})

        # 方式 B：返回后注入（不推荐 — AST 需要增强模式才可检测）
        # result = _ok(item)
        # result["format_version"] = FORMAT_VERSION

        return result
    except Exception as e:
        return _error(str(e))


@mcp.tool()
def sample_list_result() -> dict:
    """返回列表数据的标准模式。"""
    try:
        items = [{"id": "1"}, {"id": "2"}]

        return _ok(
            {
                "format_version": FORMAT_VERSION,
                "items": items,
                "total": len(items),
            }
        )
    except Exception as e:
        return _error(str(e))


# ── 模拟辅助（仅用于演示） ──


async def _fetch_some_data(query: str, limit: int) -> list:
    """模拟异步数据获取。"""
    return [{"id": i, "title": f"{query} result {i}"} for i in range(limit)]


# ── 入口点 ──────────────────────────────────────────


def main() -> None:
    """运行 MCP server（stdio 模式，供 Agora 集成）。"""
    mcp.run()


def http_main() -> None:
    """运行 MCP server（HTTP 模式）。"""
    import asyncio

    asyncio.run(mcp.run_http_async(host="127.0.0.1", port=8765))


if __name__ == "__main__":
    main()
