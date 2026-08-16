"""Serena 适配器 — LSP 符号级代码检索与分析。

Serena 是一个 MCP 工具集，提供符号级代码操作能力。
本适配器负责检测 Serena 可用性并集成到分析管线。
详细查询（find_symbol/find_referencing_symbols 等）需在对话中
通过 MCP 工具直接使用。
"""

import logging
import shutil

logger = logging.getLogger(__name__)


def get_available_tools() -> list[str]:
    """返回可用的 Serena MCP 工具列表。"""
    return [
        "find_symbol",
        "find_referencing_symbols",
        "find_implementations",
        "find_declaration",
        "get_symbols_overview",
        "get_diagnostics_for_file",
        "get_diagnostics_for_symbol",
        "rename_symbol",
        "replace_symbol_body",
        "safe_delete_symbol",
        "search_for_pattern",
        "query_project",
    ]


def check_available() -> dict:
    """检测 Serena 是否可用并返回状态（不需要 project_path）。"""
    if not shutil.which("serena"):
        return {"available": False, "indexed": 0, "tools": [], "error": "serena CLI not found"}
    return {
        "available": True,
        "indexed": 0,
        "tools": get_available_tools(),
    }
