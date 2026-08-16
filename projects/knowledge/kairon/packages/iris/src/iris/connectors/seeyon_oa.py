"""Seeyon OA connector — 致远 OA CDP 抓取 (ECCP P3 收编, N5 list 能力).

收编自 runtime/scripts/seeyon-oa-cdp-ingest.py + seeyon-auto-login-fetch.py.
原脚本: 复用 Chrome 9222 已登录 Session, 静默定位致远 OA 待办公文 tab.
N5: 迁移 CDP /json/list tab 定位逻辑到 list_items, 统一走 BaseConnector 契约.

收编理由 (fabric truth_owner: source_adapters=kairon.iris):
  致远 OA 是 knowledge_source (待办公文), 进 iris 连接器枢纽是架构正位.

边界: 本 connector 定位已登录 OA tab (如原脚本). DOM 深抓待办公文 (CDP
Runtime.evaluate) 是后续增强, 需 Chrome --remote-debugging-port=9222 + 已登录 OA.
"""

from __future__ import annotations

import json
import urllib.request
from typing import Any

from iris.base import BaseConnector
from iris.models import Note

SEEYON_CDP_PORT = 9222
SEEYON_URL_HINTS = ("10.216.16.151", "seeyon")


class SeeyonOAConnector(BaseConnector):
    """致远 OA (ECCP P3 收编, N5 list 能力: CDP 9222 共享 Session 定位待办 tab)."""

    name = "seeyon_oa"
    display_name = "致远 OA"
    connection_kind = "knowledge_source"
    protocol = "seeyon.oa.cdp/v1"
    capabilities = ("discover", "search", "read", "snapshot")
    data_classification = "internal"

    def is_available(self) -> bool:
        """检查 Chrome 9222 CDP Remote Debugging 开启."""
        try:
            # Chrome 111+ DNS rebinding 保护: CDP /json/* 拒绝 127.0.0.1 Host (404), 只接受 localhost.
            req = urllib.request.urlopen(f"http://localhost:{SEEYON_CDP_PORT}/json/version", timeout=2)
            return bool(json.loads(req.read().decode("utf-8")))
        except Exception:
            return False

    def status(self) -> dict[str, Any]:
        return {
            "cdp_port": SEEYON_CDP_PORT,
            "available": self.is_available(),
            "note": "需 Chrome --remote-debugging-port=9222 + 已登录致远 OA",
        }

    def list_items(
        self,
        limit: int = 20,
        cursor: str | None = None,
        tag: str | None = None,
        folder: str | None = None,
        subdir: str | None = None,
        chat_id: str | None = None,
    ) -> list[Note]:
        """扫 CDP /json/list 定位致远 OA 已登录 tab (收编自 seeyon-oa-cdp-ingest).

        边界: 定位 tab 级 (如原脚本); DOM 深抓待办公文需后续 CDP Runtime.evaluate.
        """
        if not self.is_available():
            return []
        try:
            req = urllib.request.urlopen(f"http://127.0.0.1:{SEEYON_CDP_PORT}/json/list", timeout=3)
            tabs = json.loads(req.read().decode("utf-8"))
        except Exception:
            return []
        items: list[Note] = []
        for tab in tabs:
            url = tab.get("url", "")
            if not any(hint in url for hint in SEEYON_URL_HINTS):
                continue
            items.append(
                Note(
                    id=tab.get("id") or url,
                    title=tab.get("title", "致远OA待办公文"),
                    platform="seeyon_oa",
                    created_at="",
                    updated_at="",
                    content=tab.get("status", "已登录 Session 页面"),
                    tags=["oa", "pending"],
                    source_path=url or "seeyon://pending",
                )
            )
            if len(items) >= limit:
                break
        return items

    def search(self, query: str, limit: int = 10) -> list[Note]:
        """简单搜索 (title/content 含 query)."""
        items = self.list_items(limit=limit * 3)
        q = query.lower()
        return [it for it in items if q in it.title.lower() or q in it.content.lower()][:limit]

    # ── P4-T5: OA Write Capability (CDP Runtime.evaluate) ──────────

    def _get_ws_url(self) -> str | None:
        """Get webSocketDebuggerUrl for the OA tab."""
        if not self.is_available():
            return None
        try:
            req = urllib.request.urlopen(f"http://localhost:{SEEYON_CDP_PORT}/json/list", timeout=3)
            tabs = json.loads(req.read().decode("utf-8"))
            for tab in tabs:
                url = tab.get("url", "")
                if any(hint in url for hint in SEEYON_URL_HINTS):
                    return tab.get("webSocketDebuggerUrl")
        except Exception:
            return None
        return None

    def _cdp_evaluate(self, expression: str) -> dict[str, Any] | None:
        """Execute JavaScript via CDP Runtime.evaluate (requires websockets lib).

        Returns result dict or None if CDP/websockets unavailable.
        """
        ws_url = self._get_ws_url()
        if not ws_url:
            return None
        try:
            import asyncio
            import json as _json

            async def _eval() -> dict[str, Any] | None:
                try:
                    import websockets
                except ImportError:
                    return None
                async with websockets.connect(ws_url) as ws:
                    msg = _json.dumps({
                        "id": 1, "method": "Runtime.evaluate",
                        "params": {"expression": expression, "returnByValue": True},
                    })
                    await ws.send(msg)
                    resp = _json.loads(await ws.recv())
                    return resp.get("result", {}).get("result", {}).get("value")

            return asyncio.run(_eval())
        except Exception:
            return None

    def submit_document(self, form_data: dict[str, str]) -> dict[str, Any]:
        """Submit a document in OA via CDP DOM manipulation (P4-T5).

        Requires: Chrome CDP 9222 + OA logged in + websockets library.
        Args:
            form_data: {field_selector: value} pairs to fill.
        Returns: {status, submitted, detail}
        """
        if not self.is_available():
            return {"status": "unavailable", "detail": "CDP 9222 not open"}

        # Fill form fields
        for selector, value in form_data.items():
            js = f"document.querySelector('{selector}').value = '{value}';"
            self._cdp_evaluate(js)

        # Click submit button (OA specific — selector needs DOM勘察)
        result = self._cdp_evaluate(
            "document.querySelector('input[type=submit], button[type=submit]')?.click() || 'no_submit_button'"
        )

        if result is None:
            return {"status": "degraded", "detail": "websockets lib not available, form filled but not submitted"}
        return {"status": "submitted", "detail": f"form submitted, result={result}"}

    def fill_form(self, form_data: dict[str, str]) -> dict[str, Any]:
        """Fill OA form fields without submitting (L2 safe action)."""
        if not self.is_available():
            return {"status": "unavailable", "detail": "CDP 9222 not open"}
        filled = 0
        for selector, value in form_data.items():
            js = f"document.querySelector('{selector}').value = '{value}';"
            if self._cdp_evaluate(js) is not None:
                filled += 1
        return {"status": "filled", "fields_filled": filled, "total": len(form_data)}

