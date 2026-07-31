"""ReachBridge-Enterprise — 矩阵级多用户多设备多应用触达中台包

包含 HermesRelayProvider: 物理利用 Hermes 守护进程作为中转站 (Relay Station)，
将 BOS Neural Mesh 的通知中转推送到人类微信中。

v3.2 (Hermes Relay Station Integrated) | 2026-07-31
"""

from __future__ import annotations

import json
import os
import subprocess
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

HERMES_BIN = Path("/opt/homebrew/bin/hermes")
HERMES_DIR = Path.home() / ".hermes"
RELAY_FILE = HERMES_DIR / "outbound_relay.json"


class ScenarioLevel(Enum):
    EMERGENCY = "emergency"  # 阻断预警：多通道强弹窗
    ACTIONABLE = "actionable" # 需打钩决策：发送带按钮消息
    BULLETIN = "bulletin"   # 消息摘要：合并静默推送
    SILENT = "silent"       # 仅静默落盘日志，不弹窗


@dataclass
class ReachPayload:
    title: str
    body: str
    app_id: str = "app_default_metaos"       # 1. 多应用 ID
    user_id: str = "usr_primary_owner"       # 2. 多用户 ID
    scenario: ScenarioLevel = ScenarioLevel.ACTIONABLE # 3. 多场景级
    action_url: str | None = None
    target_devices: list[str] = field(default_factory=lambda: ["desktop", "mobile"])
    target_channels: list[str] = field(default_factory=lambda: ["mac_native", "hermes_relay"])


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


class HermesRelayProvider:
    """物理 Hermes 中转站 Provider (利用 Hermes Gateway 作为中流转发枢纽)."""

    def send(self, payload: ReachPayload) -> bool:
        HERMES_DIR.mkdir(parents=True, exist_ok=True)
        relay_data = {
            "app_id": payload.app_id,
            "user_id": payload.user_id,
            "title": payload.title,
            "body": payload.body,
            "action_url": payload.action_url,
            "timestamp": payload.scenario.value
        }

        try:
            # 1. 物理写入 ~/.hermes/outbound_relay.json 中转文件
            RELAY_FILE.write_text(json.dumps(relay_data, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"✅ [ReachBridge] HermesRelayProvider 中转写入成功 ──► ~/.hermes/outbound_relay.json (App: {payload.app_id})")

            # 2. 如果 Hermes 在轨，触发轻量 relay 信号
            if HERMES_BIN.exists():
                prompt = f"【Hermes中转消息】[{payload.title}] {payload.body}"
                subprocess.run([str(HERMES_BIN), "--source", "tool", "-z", prompt], capture_output=True, text=True, timeout=5)
                print("✅ [ReachBridge] Hermes Relay 触达中转指令完成")

            return True
        except Exception as e:
            print(f"⚠️ HermesRelayProvider 降级处理: {e}")
            return False


class ReachGateway:
    """矩阵级统一触达中台管理器."""

    def __init__(self) -> None:
        self.mac_provider = MacNativeProvider()
        self.hermes_relay = HermesRelayProvider()

    def dispatch_payload(self, payload: ReachPayload) -> bool:
        print(f"📲 [ReachGateway Dispatching] App={payload.app_id} | Title={payload.title}")

        if "mac_native" in payload.target_channels:
            self.mac_provider.send(payload)

        if "hermes_relay" in payload.target_channels:
            self.hermes_relay.send(payload)

        return True
