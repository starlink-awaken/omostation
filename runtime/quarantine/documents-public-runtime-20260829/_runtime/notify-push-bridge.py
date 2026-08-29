#!/usr/bin/env python3
"""notify-push-bridge.py — 社交工具与手机端推送适配器

功能: 接收系统产生的关键决策、简报与卡片更新，
通过飞书/企微 Webhook、Telegram Bot 或 Bark 极速推送给人类。

v1.0 | 2026-07-30
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


def push_macos_native(title: str, body: str) -> bool:
    try:
        script = f'display notification "{body}" with title "{title}" subtitle "BOS Neural Mesh"'
        subprocess.run(["osascript", "-e", script], check=False)
        return True
    except Exception:
        return False


def send_push(title: str, body: str, channel: str = "local", action_url: str | None = None) -> bool:
    """发送推送消息到社交工具/手机端 (支持一键快捷 Click Action)."""
    timestamp = datetime.now(timezone.utc).strftime("%H:%M:%S")
    print(f"\n📲 [PUSH MESSAGE @ {timestamp}] [{title}]\n{body}")
    if action_url:
        print(f"👉 [一键快捷 Action 点击链接]: {action_url}\n")

    push_macos_native(title, body)

    bark_key = os.environ.get("BARK_KEY")
    if bark_key and channel in ("bark", "all"):
        try:
            url = f"https://api.day.app/{bark_key}/{urllib.parse.quote(title)}/{urllib.parse.quote(body)}"
            if action_url:
                url += f"?url={urllib.parse.quote(action_url)}"
            urllib.request.urlopen(url, timeout=5)
            print("✅ Bark 手机端弹窗推送成功 (带快捷 Action 按钮)")
        except Exception as e:
            print(f"⚠️ Bark 推送失败: {e}")

    # 3. 飞书 / 企业微信 Webhook
    webhook_url = os.environ.get("FEISHU_WEBHOOK") or os.environ.get("WECHAT_WEBHOOK")
    if webhook_url and channel in ("webhook", "all"):
        try:
            payload = {
                "msg_type": "text",
                "content": {"text": f"📢 【MetaOS 协同推送】{title}\n\n{body}"}
            }
            req = urllib.request.Request(
                webhook_url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            urllib.request.urlopen(req, timeout=5)
            print("✅ 社交工具 Webhook 推送成功")
        except Exception as e:
            print(f"⚠️ Webhook 推送失败: {e}")

    return True


def main() -> int:
    if len(sys.argv) < 3:
        print("用法: python3 notify-push-bridge.py <title> <body> [channel]")
        return 1
    title = sys.argv[1]
    body = sys.argv[2]
    channel = sys.argv[3] if len(sys.argv) > 3 else "local"
    send_push(title, body, channel)
    return 0


if __name__ == "__main__":
    sys.exit(main())
