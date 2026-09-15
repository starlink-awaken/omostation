"""Feishu(Lark) connector — 通过 Webhook 发送消息"""

from __future__ import annotations

import json
import os
import urllib.request
from typing import Any

from iris.base import BaseConnector, SyncResult


class FeishuConnector(BaseConnector):
    name = "feishu"
    display_name = "Feishu (Lark)"

    def is_available(self) -> bool:
        return bool(os.environ.get("FEISHU_WEBHOOK_URL"))

    def connect(self) -> dict:
        return {"connected": self.is_available()}

    def send(self, message: str) -> dict:
        url = os.environ.get("FEISHU_WEBHOOK_URL", "")
        if not url:
            return {"error": "FEISHU_WEBHOOK_URL not set"}
        data = json.dumps({"msg_type": "text", "content": {"text": message[:2000]}}).encode()
        try:
            req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=10):
                return {"sent": True}
        except Exception as e:
            return {"error": str(e)}

    def status(self) -> dict[str, Any]:
        ok = self.is_available()
        return {
            "available": ok,
            "webhook_configured": ok,
            "setup": "export FEISHU_WEBHOOK_URL='https://open.feishu.cn/open-apis/bot/v2/hook/...'",
        }

    def sync(self, dry_run: bool = False) -> SyncResult:
        if not self.is_available():
            return SyncResult(
                connector_name=self.name,
                success=False,
                message="FEISHU_WEBHOOK_URL not set",
            )
        return SyncResult(
            connector_name=self.name,
            success=True,
            message="Feishu webhook ready (push-only connector; no pull sync)",
        )
