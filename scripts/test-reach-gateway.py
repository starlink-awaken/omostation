#!/usr/bin/env python3
"""test-reach-gateway.py — 物理真实消息下发测试"""

import sys
from datetime import datetime, timezone
from pathlib import Path

# 添加精确包路径
sys.path.insert(0, "/Users/xiamingxing/Workspace/projects/runtime/packages/reach/src")

from reach_gateway import ReachGateway, ReachPayload, ScenarioLevel


def main() -> int:
    now_str = datetime.now(timezone.utc).strftime("%H:%M:%S")
    gateway = ReachGateway()

    payload = ReachPayload(
        app_id="app_metaos_cockpit",
        user_id="usr_xiamingxing",
        scenario=ScenarioLevel.EMERGENCY,
        title=f"【MetaOS 物理发信测试 @ {now_str}】",
        body="BOS Neural Mesh 触达中台已成功调起！请检查 Mac 屏幕右上角横幅与微信！",
        action_url=f"http://localhost:8183/action/approve?id=TEST-{now_str}",
        target_channels=["mac_native", "hermes_wechat"]
    )

    print(f"🚀 物理发起实时下发测试消息: {payload.title}")
    gateway.dispatch_payload(payload)
    return 0


if __name__ == "__main__":
    sys.exit(main())
