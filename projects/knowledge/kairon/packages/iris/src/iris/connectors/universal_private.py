"""Universal Private connector — 360° 本地私有源 (ECCP N4 收编).

收编自 runtime/scripts/universal-private-ingest.py (5 源):
  1. Chrome 浏览历史 (Chrome History DB)
  2. iPhone SMS 运营商短信 (chat.db)
  3. Hermes 微信网关消息 (state.db)
  4. 原生 Mac 微信接收文件/公文 (WeChat Native Files)
  5. 原生 Mac 微信 UI 零解密聊天 (Accessibility UI Parser)

本 connector: health (5 源可用性) + descriptor; list 留后续 (各源抓取逻辑迁移).
kind=data_source (区别于 knowledge_source, 私有原始数据).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from iris.base import BaseConnector

# 5 源路径 (macOS 标准 + Hermes)
HOME = Path.home()
SOURCES = {
    "chrome_history": HOME / "Library/Application Support/Google/Chrome/Default/History",
    "iphone_sms_chatdb": HOME / "Library/Application Support/MobileSync/Backup",  # iTunes 备份
    "hermes_wechat": HOME / "Library/Containers/com.tencent.xinWeChat",  # Mac 微信
    "wechat_native_files": HOME / "Library/Containers/com.tencent.xinWeChat/Data/Library/Application Support",
    "mac_keychain": HOME / "Library/Keychains",  # Accessibility UI 需 keychain 权限
}


class UniversalPrivateConnector(BaseConnector):
    """360° 本地私有源 (ECCP N4 收编, data_source)."""

    name = "universal_private"
    display_name = "Universal Private (360° 本地源)"
    connection_kind = "data_source"
    protocol = "universal.private/v1"
    capabilities = ("discover", "snapshot")
    data_classification = "private"

    def is_available(self) -> bool:
        """至少 1 源可用."""
        return any(p.exists() for p in SOURCES.values())

    def status(self) -> dict[str, Any]:
        """5 源可用性明细."""
        return {
            "sources": {k: v.exists() for k, v in SOURCES.items()},
            "available_sources": sum(1 for v in SOURCES.values() if v.exists()),
            "available": self.is_available(),
            "note": "list 留后续 (各源抓取逻辑迁移自 universal-private-ingest.py)",
        }
