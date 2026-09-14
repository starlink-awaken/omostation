"""CUA Browser connector — 浏览器自动化 (ECCP P3 收编, tool_capability).

收编 cua-driver (MCP server, 跨平台 computer-use).
kind=tool_capability (非 knowledge_source), 区别于其他 iris connector.
本 connector: health (node/cua 可用) + descriptor; invoke 留后续 (MCP 包装).
"""

from __future__ import annotations

import shutil
from typing import Any

from iris.base import BaseConnector


class CuaBrowserConnector(BaseConnector):
    """CUA 浏览器自动化 (ECCP P3 收编, tool_capability)."""

    name = "cua_browser"
    display_name = "CUA Browser"
    connection_kind = "tool_capability"
    protocol = "cua.browser/v1"
    capabilities = ("discover", "invoke")
    data_classification = "private"

    def is_available(self) -> bool:
        """检查 node 可用 (cua-driver MCP 依赖 node 运行时)."""
        return shutil.which("node") is not None

    def status(self) -> dict[str, Any]:
        return {
            "kind": "browser_tool_capability",
            "available": self.is_available(),
            "node_path": shutil.which("node") or "",
            "note": "cua-driver MCP server, invoke 留后续包装",
        }
