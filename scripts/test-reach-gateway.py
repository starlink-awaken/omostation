#!/usr/bin/env python3
"""test-reach-gateway.py — ReachBridge 物理 Hermes 中转站 (Relay Station) 实操测试"""

import sys
from pathlib import Path

sys.path.insert(0, "/Users/xiamingxing/Workspace/projects/runtime/packages/reach/src")

from reach_gateway import ReachGateway, ReachPayload, ScenarioLevel


def main() -> int:
    gateway = ReachGateway()

    payload = ReachPayload(
        app_id="app_weijian_governance",
        user_id="usr_weijian_supervisor",
        scenario=ScenarioLevel.EMERGENCY,
        title="【Hermes 中转测试】",
        body="公文草案抓取完成，物理通过 Hermes 守护进程中转流发！",
        action_url="http://localhost:8183/action/approve?id=RELAY-20260731",
        target_channels=["mac_native", "hermes_relay"]
    )

    print("--- 物理测试: 通过 Hermes 作为 Relay 中转站发起触达 ---")
    gateway.dispatch_payload(payload)
    return 0


if __name__ == "__main__":
    sys.exit(main())
