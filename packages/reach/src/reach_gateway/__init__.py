"""ReachBridge — 多渠道物理触达网关模块

提供 ReachGateway, ReachPayload, ScenarioLevel 的物理封装。
"""

from __future__ import annotations

import os
import subprocess
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

HERMES_BIN = Path("/opt/homebrew/bin/hermes")


class ScenarioLevel(Enum):
    EMERGENCY = "emergency"  # 阻断预警：多通道强弹窗
    ACTIONABLE = "actionable" # 需打钩决策：发送带按钮消息
    BULLETIN = "bulletin"   # 消息摘要：合并静默推送
    SILENT = "silent"       # 仅静默落盘日志，不弹窗


@dataclass
class ReachPayload:
    title: str
    body: str
    app_id: str = "app_default_metaos"
    user_id: str = "usr_primary_owner"
    scenario: ScenarioLevel = ScenarioLevel.ACTIONABLE
    action_url: str | None = None
    target_devices: list[str] = field(default_factory=lambda: ["desktop", "mobile"])
    target_channels: list[str] = field(default_factory=lambda: ["mac_native", "hermes_wechat"])


class MacNativeProvider:
    """物理 macOS 原生 AppleScript 屏幕通知横幅 Provider."""

    def send(self, payload: ReachPayload) -> bool:
        try:
            subtitle = f"{payload.app_id} | {payload.scenario.value}"
            script = f'display notification "{payload.body}" with title "{payload.title}" subtitle "{subtitle}"'
            subprocess.run(["osascript", "-e", script], check=False)
            print(f"✅ [ReachBridge] MacNativeProvider 系统横幅已弹窗推送: {payload.title}")
            return True
        except Exception as e:
            print(f"⚠️ MacNativeProvider 异常: {e}")
            return False


class HermesWechatProvider:
    """物理本地 Hermes WeChat Gateway (/opt/homebrew/bin/hermes --profile exec) 通道 Provider."""

    def send(self, payload: ReachPayload) -> bool:
        if not HERMES_BIN.exists():
            print("ℹ️ 本地未找到 /opt/homebrew/bin/hermes")
            return False

        try:
            prompt = f"【{payload.title}】\n{payload.body}"
            if payload.action_url:
                prompt += f"\n👉 点击操作: {payload.action_url}"

            res = subprocess.run(
                [str(HERMES_BIN), "--profile", "exec", "-z", prompt],
                capture_output=True,
                text=True,
                timeout=10
            )
            print(f"✅ [ReachBridge] HermesWechatProvider (Profile: exec) 微信通道下发成功！ (Return: {res.returncode})")
            return True
        except Exception as e:
            print(f"⚠️ HermesWechatProvider 调起异常: {e}")
            return False


class ReachGateway:
    """矩阵级统一触达中台管理器."""

    def __init__(self) -> None:
        self.mac_provider = MacNativeProvider()
        self.hermes_provider = HermesWechatProvider()

    def dispatch_payload(self, payload: ReachPayload) -> bool:
        print(f"📲 [ReachGateway Dispatching] App={payload.app_id} | Title={payload.title}")

        if "mac_native" in payload.target_channels:
            self.mac_provider.send(payload)

        if "hermes_wechat" in payload.target_channels:
            self.hermes_provider.send(payload)

        return True
