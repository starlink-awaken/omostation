"""Forge 集市 MCP tools — agora 侧 (P33-W5 战役 3).

提供 3 个 MCP 工具:
  - forge_load(name=None)  : 从 .omo/capabilities/market.json 加载工具到 agora
  - forge_list()           : 列出已加载的 forge 工具
  - forge_unload(name)     : 从 agora 卸载工具

P33-W4 战役 1 已让 21 BOS URI 真活 (静态注册).
P33-W5 战役 3 让 URI 集 *热加载* — 不重启 agora, 动态注入 POC_SERVICES.
"""

from __future__ import annotations

from fastmcp import FastMCP

from agora.mcp.forge_loader import (
    CAPS_ROOT,
    install_local_tool,
    list_market_tools,
    loader,
    remove_tool,
)
from agora.mcp.tools_template import FORMAT_VERSION, _error, _ok

# ── MCP 实例 ─────────────────────────────────────────
mcp = FastMCP("agora-forge-market")


# ── 工具 ───────────────────────────────────────────
@mcp.tool()
def forge_load(name: str | None = None) -> dict:
    """从 .omo/capabilities/market.json 加载 forge 工具.

    Args:
        name: 工具名. None = 加载全部已注册工具.

    Returns:
        {
          "loaded": [{"loaded": "xxx", "bos_uri": "..."}],  // 单条
          或
          "loaded": [{...}, {...}]                            // 全部
        }
    """
    try:
        if name:
            market = list_market_tools()
            tool = next((t for t in market if t.get("name") == name), None)
            if tool is None:
                return _error(
                    f"tool_not_found: {name} (registered: {[t.get('name') for t in market]})"
                )
            result = loader.load_tool(tool)
            if "error" in result:
                return _error(result["error"])
            return _ok(
                {
                    "format_version": FORMAT_VERSION,
                    "result": result,
                }
            )

        results = loader.load_from_market()
        return _ok(
            {
                "format_version": FORMAT_VERSION,
                "loaded_count": len(results),
                "results": results,
            }
        )
    except Exception as exc:  # noqa: BLE001
        return _error(f"forge_load_failed: {exc}")


@mcp.tool()
def forge_list() -> dict:
    """列出已加载的 forge 工具 (P33-W5 战役 3 动态注入部分)."""
    try:
        loaded = loader.list_loaded()
        return _ok(
            {
                "format_version": FORMAT_VERSION,
                "count": len(loaded),
                "loaded": loaded,
            }
        )
    except Exception as exc:  # noqa: BLE001
        return _error(f"forge_list_failed: {exc}")


@mcp.tool()
def forge_unload(name: str) -> dict:
    """从 agora 卸载 forge 工具.

    Args:
        name: 工具名.
    """
    try:
        success = loader.unload_tool(name)
        if not success:
            return _error(f"unload_failed_or_not_loaded: {name}")
        return _ok(
            {
                "format_version": FORMAT_VERSION,
                "unloaded": name,
            }
        )
    except Exception as exc:  # noqa: BLE001
        return _error(f"forge_unload_failed: {exc}")


@mcp.tool()
def forge_install(
    name: str,
    source_path: str,
    bos_uri: str = "",
    description: str = "",
) -> dict:
    """安装新工具到 .omo/capabilities/ + 自动注册到 agora.

    Args:
        name: kebab-case 工具名.
        source_path: 源路径 (文件或目录).
        bos_uri: 关联 BOS URI (e.g. 'bos://memory/kos/search'). 可选.
        description: 工具描述.

    Returns:
        {"installed": name, "path": "...", "bos_uri": "..."}
    """
    try:
        result = install_local_tool(name, source_path, bos_uri, description)
        if "error" in result:
            return _error(result["error"])
        return _ok(
            {
                "format_version": FORMAT_VERSION,
                "result": result,
            }
        )
    except Exception as exc:  # noqa: BLE001
        return _error(f"forge_install_failed: {exc}")


@mcp.tool()
def forge_remove(name: str) -> dict:
    """从 .omo/capabilities/ 移除工具.

    Args:
        name: 工具名.
    """
    try:
        success = remove_tool(name)
        if not success:
            return _error(f"remove_failed_or_not_found: {name}")
        # 同步: 卸载已加载的
        loader.unload_tool(name)
        return _ok(
            {
                "format_version": FORMAT_VERSION,
                "removed": name,
            }
        )
    except Exception as exc:  # noqa: BLE001
        return _error(f"forge_remove_failed: {exc}")


@mcp.tool()
def forge_market() -> dict:
    """列出 .omo/capabilities/market.json 注册表 (含未加载的)."""
    try:
        market = list_market_tools()
        return _ok(
            {
                "format_version": FORMAT_VERSION,
                "count": len(market),
                "market_root": str(CAPS_ROOT),
                "tools": market,
            }
        )
    except Exception as exc:  # noqa: BLE001
        return _error(f"forge_market_failed: {exc}")


def main() -> None:
    """运行 MCP server (stdio 模式)."""
    mcp.run()


if __name__ == "__main__":
    main()
