"""P4: 统一告警入口测试.

覆盖:
- send_alert 发布 EventBus 事件
- 防抖: 同 key 300s 内只发一次
- force=True 绕过防抖
- 熔断 callback 触发统一告警 (circuit:open)
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch


def _mk_bus_published():
    """构造假 event_bus 收集发布事件."""
    published = []
    fake_bus = MagicMock()
    fake_bus.publish.side_effect = lambda ev: published.append(ev)
    return published, fake_bus


def test_send_alert_publishes_event():
    """send_alert 发布 EventBus 事件."""
    from agora.mcp import agora_alerts as aa

    published, fake_bus = _mk_bus_published()
    with patch("agora.core.state.get_event_bus", return_value=fake_bus):
        aa._throttle_ts.clear()
        aa.send_alert(
            "warning", "quota:blocked", {"caller_id": "a", "today_cost": 2.0},
            caller_key="quota:a", force=True,
        )
    assert any("quota:blocked" in p.get("type", "") for p in published)


def test_throttle_blocks_repeat():
    """同 key 防抖: 第二次 (未过窗口) 不发."""
    from agora.mcp import agora_alerts as aa

    published, fake_bus = _mk_bus_published()
    with patch("agora.core.state.get_event_bus", return_value=fake_bus):
        aa._throttle_ts.clear()
        aa.send_alert("warning", "health:degraded", {"issues": ["x"]}, caller_key="health:degraded")
        aa.send_alert("warning", "health:degraded", {"issues": ["x"]}, caller_key="health:degraded")
    assert sum(1 for p in published if p.get("type") == "health:degraded") == 1


def test_force_bypasses_throttle():
    """force=True 绕过防抖."""
    from agora.mcp import agora_alerts as aa

    published, fake_bus = _mk_bus_published()
    with patch("agora.core.state.get_event_bus", return_value=fake_bus):
        aa._throttle_ts.clear()
        aa.send_alert("warning", "e1", {}, caller_key="k", force=True)
        aa.send_alert("warning", "e1", {}, caller_key="k", force=True)
    assert sum(1 for p in published if p.get("type") == "e1") == 2


def test_circuit_callback_triggers_alert():
    """熔断打开 → 统一告警 (circuit:open)."""
    from agora.mcp import bos_middleware as bm

    published, fake_bus = _mk_bus_published()
    with patch("agora.core.state.get_event_bus", return_value=fake_bus):
        from agora.mcp import agora_alerts as aa

        aa._throttle_ts.clear()
        # 连续失败触发熔断 OPEN
        for _ in range(4):
            bm.bos_circuit_breaker.record_failure("bos://memory/kos/search")
    assert any("circuit:open" in p.get("type", "") for p in published)
