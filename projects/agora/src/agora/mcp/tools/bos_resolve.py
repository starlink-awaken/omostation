"""BOS Resolve MCP Tool — agora 侧 (P33-W4 战役 1).

MCP 工具入口: 把 BOS URI 解析/调用 暴露为 fastmcp tool.
战役 1 核心: omostation 进程间路由枢纽.

提供 2 个 tool:
  - bos_resolve(uri, *args, **kwargs)  → 实际调用结果
  - bos_list()                         → 注册表 + 实时状态
"""

from __future__ import annotations

from fastmcp import FastMCP

from agora.mcp.bos_resolver import (
    list_services,
    parse_bos_uri,
    protocol_self_check,
    resolve_bos_uri,
)
from agora.mcp.tools_template import FORMAT_VERSION, _error, _ok

# ── MCP 实例 ─────────────────────────────────────────
mcp = FastMCP("agora-bos-resolver")


@mcp.tool()
def bos_resolve(uri: str) -> dict:
    """解析 BOS URI 到实际 MCP 调用 (战役 1 入口).

    Args:
        uri: bos://<domain>/<package>/<action> 形式 (e.g. bos://memory/kos/search)
    """
    try:
        # 同步包装 async resolve_bos_uri
        import asyncio as _aio

        result = _aio.run(resolve_bos_uri(uri))
        return _ok(
            {
                "format_version": FORMAT_VERSION,
                "uri": uri,
                "resolution": result,
            }
        )
    except ValueError as ve:
        return _error(f"invalid_bos_uri: {ve}")
    except Exception as exc:  # noqa: BLE001
        return _error(f"bos_resolve_failed: {exc}")


@mcp.tool()
def bos_list() -> dict:
    """列出所有已注册 BOS services (11 POC) + 实时状态."""
    try:
        services = list_services()
        return _ok(
            {
                "format_version": FORMAT_VERSION,
                "count": len(services),
                "services": services,
                "self_check": protocol_self_check(),
            }
        )
    except Exception as exc:  # noqa: BLE001
        return _error(f"bos_list_failed: {exc}")


@mcp.tool()
def bos_parse(uri: str) -> dict:
    """解析 BOS URI 到 3 段 (domain/package/action), 不实际调用.

    Args:
        uri: bos://<domain>/<package>/<action>
    """
    try:
        parsed = parse_bos_uri(uri)
        return _ok(
            {
                "format_version": FORMAT_VERSION,
                "uri": uri,
                "parsed": parsed,
            }
        )
    except ValueError as ve:
        return _error(f"invalid_bos_uri: {ve}")


def main() -> None:
    """运行 MCP server (stdio 模式)."""
    mcp.run()


if __name__ == "__main__":
    main()
