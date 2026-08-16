"""DingTalk connector — 通过 Webhook 发送消息通知"""

from __future__ import annotations

import json
import os
import urllib.request
from typing import Any, cast

from iris.base import BaseConnector, SyncResult


class DingTalkConnector(BaseConnector):
    name = "dingtalk"
    display_name = "DingTalk"

    def is_available(self) -> bool:
        return bool(os.environ.get("DINGTALK_WEBHOOK_URL"))

    def connect(self) -> dict:
        return {"connected": self.is_available()}

    def send(self, message: str) -> dict:
        url = os.environ.get("DINGTALK_WEBHOOK_URL", "")
        if not url:
            return {"error": "DINGTALK_WEBHOOK_URL not set"}
        data = json.dumps({"msgtype": "text", "text": {"content": message[:2000]}}).encode()
        try:
            req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})  # noqa: S310
            with urllib.request.urlopen(req, timeout=10) as r:  # noqa: S310
                return cast("dict[Any, Any]", json.loads(r.read()))
        except Exception as e:
            return {"error": str(e)}

    def status(self) -> dict[str, Any]:
        ok = self.is_available()
        return {
            "available": ok,
            "webhook_configured": ok,
            "setup": "export DINGTALK_WEBHOOK_URL='https://oapi.dingtalk.com/robot/send?access_token=...'",
        }

    def sync(self, dry_run: bool = False) -> SyncResult:
        if not self.is_available():
            return SyncResult(
                connector_name=self.name,
                success=False,
                message="DINGTALK_WEBHOOK_URL not set",
            )
        return SyncResult(
            connector_name=self.name,
            success=True,
            message="DingTalk webhook ready (push-only connector; no pull sync)",
        )
