"""ReachBridge-Enterprise — 矩阵级多用户多设备多应用触达中台包

包含 HermesRelayProvider: 物理利用 Hermes 守护进程作为中转站 (Relay Station)，
将 BOS Neural Mesh 的通知中转推送到人类微信中。

v3.2 (Hermes Relay Station Integrated) | 2026-07-31
"""

from __future__ import annotations

import json
import os
import subprocess
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

HERMES_BIN = Path(os.environ.get("BOS_HERMES_BIN", "/opt/homebrew/bin/hermes"))
HERMES_DIR = Path(os.environ.get("BOS_HERMES_DIR", str(Path.home() / ".hermes")))
RELAY_FILE = Path(
    os.environ.get("BOS_HERMES_RELAY_FILE", str(HERMES_DIR / "outbound_relay.json"))
)


class ScenarioLevel(Enum):
    EMERGENCY = "emergency"  # 阻断预警：多通道强弹窗
    ACTIONABLE = "actionable"  # 需打钩决策：发送带按钮消息
    BULLETIN = "bulletin"  # 消息摘要：合并静默推送
    SILENT = "silent"  # 仅静默落盘日志，不弹窗


@dataclass
class ReachPayload:
    title: str
    body: str
    app_id: str = "app_default_metaos"  # 1. 多应用 ID
    user_id: str = "usr_primary_owner"  # 2. 多用户 ID
    scenario: ScenarioLevel = ScenarioLevel.ACTIONABLE  # 3. 多场景级
    action_url: str | None = None
    target_devices: list[str] = field(default_factory=lambda: ["desktop", "mobile"])
    target_channels: list[str] = field(
        default_factory=lambda: ["mac_native", "hermes_relay"]
    )
    dispatch_id: str | None = None


class MacNativeProvider:
    """物理 macOS 原生 AppleScript 屏幕通知横幅 Provider."""

    def send(self, payload: ReachPayload) -> bool:
        try:
            subtitle = f"{payload.app_id} | {payload.scenario.value}"
            script = (
                f"display notification {json.dumps(payload.body, ensure_ascii=False)} "
                f"with title {json.dumps(payload.title, ensure_ascii=False)} "
                f"subtitle {json.dumps(subtitle, ensure_ascii=False)}"
            )
            result = subprocess.run(
                ["osascript", "-e", script], check=False, capture_output=True, text=True
            )
            return result.returncode == 0
        except (OSError, subprocess.SubprocessError) as e:
            print(f"⚠️ MacNativeProvider 异常: {e}")
            return False


class HermesRelayProvider:
    """物理 Hermes 中转站 Provider (利用 Hermes Gateway 作为中流转发枢纽)."""

    def send(self, payload: ReachPayload) -> bool:
        HERMES_DIR.mkdir(parents=True, exist_ok=True)
        relay_data = {
            "schema": "reachbridge.relay.v1",
            "dispatch_id": payload.dispatch_id,
            "app_id": payload.app_id,
            "user_id": payload.user_id,
            "title": payload.title,
            "body": payload.body,
            "action_url": payload.action_url,
            "scenario": payload.scenario.value,
        }

        try:
            if RELAY_FILE.exists():
                existing = json.loads(RELAY_FILE.read_text(encoding="utf-8"))
                if existing.get("dispatch_id") == payload.dispatch_id:
                    return True

            # Write atomically so the Hermes consumer never observes a partial envelope.
            temporary = RELAY_FILE.with_suffix(".tmp")
            temporary.write_text(
                json.dumps(relay_data, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            temporary.replace(RELAY_FILE)

            # A relay file is a queued handoff. If Hermes is installed, require
            # its signal command to succeed as well.
            if HERMES_BIN.exists():
                prompt = f"【Hermes中转消息】[{payload.title}] {payload.body}"
                result = subprocess.run(
                    [str(HERMES_BIN), "--source", "tool", "-z", prompt],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    check=False,
                )
                return result.returncode == 0

            return RELAY_FILE.is_file()
        except (OSError, subprocess.SubprocessError, json.JSONDecodeError) as e:
            print(f"⚠️ HermesRelayProvider 降级处理: {e}")
            return False


class ReachGateway:
    """矩阵级统一触达中台管理器."""

    def __init__(self) -> None:
        self.mac_provider = MacNativeProvider()
        self.hermes_relay = HermesRelayProvider()

    def dispatch_payload(self, payload: ReachPayload) -> bool:
        results = []
        if "mac_native" in payload.target_channels:
            results.append(self.mac_provider.send(payload))

        if "hermes_relay" in payload.target_channels:
            results.append(self.hermes_relay.send(payload))

        return bool(results) and all(results)


def dispatch_http(
    endpoint: str, token: str, manifest: dict[str, object], timeout: int
) -> dict[str, object]:
    """Send the redacted manifest to a configured enterprise endpoint."""
    body = json.dumps(manifest, ensure_ascii=False).encode("utf-8")
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Idempotency-Key": str(manifest["dispatch_id"]),
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(
        endpoint, data=body, headers=headers, method="POST"
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read(1024 * 1024).decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            f"ReachBridge HTTP dispatch failed: {type(exc).__name__}"
        ) from exc
    if (
        not isinstance(payload, dict)
        or payload.get("dispatch_id") != manifest["dispatch_id"]
    ):
        raise RuntimeError("ReachBridge response did not confirm dispatch_id")
    return payload
