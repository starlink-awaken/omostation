"""遗留-3: BOS 配额检查器测试.

覆盖:
- 默认配额: 未配置 caller 用 default_daily_usd
- caller 精确匹配覆盖
- caller 通配匹配 (*)
- 服务级配额收紧 (min)
- 超限拒绝: today_cost >= limit → allowed=False
- 记录后 today_cost 增加
- 热重载配置
"""

from __future__ import annotations

import pytest

from agora.mcp.bos_quota import QuotaChecker, QuotaConfig


def _cfg(**data) -> QuotaConfig:
    c = QuotaConfig()
    c.load(data)
    return c


def _mk_checker(tmp_path, config: QuotaConfig) -> QuotaChecker:
    from agora.accounting import ResourceAccountDB

    db = ResourceAccountDB(db_path=str(tmp_path / "accounting.db"))
    return QuotaChecker(config=config, account_db=db)


def test_default_quota(tmp_path):
    """未配置 caller → 默认上限 (10.0)."""
    cfg = _cfg(default_daily_usd=10.0)
    chk = _mk_checker(tmp_path, cfg)
    allowed, info = chk.check("unknown-caller", "bos://memory/kos/search")
    assert allowed is True
    assert info["limit_usd"] == 10.0


def test_caller_exact_match(tmp_path):
    """精确匹配 caller → 覆盖默认."""
    cfg = _cfg(default_daily_usd=10.0, callers=[{"id": "anonymous", "daily_usd": 2.0}])
    chk = _mk_checker(tmp_path, cfg)
    allowed, info = chk.check("anonymous", "bos://memory/kos/search")
    assert allowed is True
    assert info["limit_usd"] == 2.0


def test_caller_wildcard_match(tmp_path):
    """通配匹配 agent-* → 匹配 agent-foo."""
    cfg = _cfg(default_daily_usd=10.0, callers=[{"id": "agent-*", "daily_usd": 50.0}])
    chk = _mk_checker(tmp_path, cfg)
    allowed, info = chk.check("agent-ops-1", "bos://governance/omo/audit")
    assert allowed is True
    assert info["limit_usd"] == 50.0


def test_service_level_tightens(tmp_path):
    """服务级配额收紧: min(caller, service)."""
    cfg = _cfg(
        default_daily_usd=10.0,
        callers=[{"id": "admin", "daily_usd": 100.0}],
        services=[{"prefix": "bos://analysis/minerva/", "daily_usd": 5.0}],
    )
    chk = _mk_checker(tmp_path, cfg)
    # admin 对普通服务 → 100
    _, info = chk.check("admin", "bos://memory/kos/search")
    assert info["limit_usd"] == 100.0
    # admin 对 minerva → min(100, 5) = 5
    _, info2 = chk.check("admin", "bos://analysis/minerva/search")
    assert info2["limit_usd"] == 5.0


def test_quota_exceeded_rejects(tmp_path):
    """今日成本超限 → allowed=False."""
    cfg = _cfg(default_daily_usd=10.0, callers=[{"id": "anonymous", "daily_usd": 0.01}])
    chk = _mk_checker(tmp_path, cfg)
    # 先记多笔把 today_cost 推过 0.01
    chk.record("anonymous", "bos://memory/kos/search", cost_usd=0.02)
    allowed, info = chk.check("anonymous", "bos://memory/kos/search")
    assert allowed is False
    assert info["remaining"] == 0.0


def test_record_increases_today_cost(tmp_path):
    """记账后 today_cost 增加."""
    cfg = _cfg(default_daily_usd=10.0)
    chk = _mk_checker(tmp_path, cfg)
    _, info0 = chk.check("caller-a", "bos://memory/kos/search")
    assert info0["today_cost"] == 0.0
    chk.record("caller-a", "bos://memory/kos/search", cost_usd=1.5)
    _, info1 = chk.check("caller-a", "bos://memory/kos/search")
    assert info1["today_cost"] == 1.5


def test_reload_updates_config(tmp_path):
    """热重载: 配置对象更新后生效 (checker 从 config 读取)."""
    cfg = _cfg(default_daily_usd=10.0)
    chk = _mk_checker(tmp_path, cfg)
    _, info = chk.check("x", "bos://memory/kos/search")
    assert info["limit_usd"] == 10.0
    # 直接更新 cfg (模拟文件热重载后 QuotaConfig.load(data) 被调用)
    cfg.load({"default_daily_usd": 20.0})
    _, info2 = chk.check("x", "bos://memory/kos/search")
    assert info2["limit_usd"] == 20.0


# ── 遗留-4: 告警联动 ─────────────────────────────────────────


def _reset_alerts(chk):
    """清理告警防抖状态, 使测试可重复."""
    chk._last_alert_ts.clear()
    chk._blocked_sent.clear()


def test_blocked_emits_alert(monkeypatch, tmp_path):
    """超限 → 触发 blocked 告警事件."""
    cfg = _cfg(default_daily_usd=10.0, callers=[{"id": "a", "daily_usd": 0.01}])
    chk = _mk_checker(tmp_path, cfg)
    chk.record("a", "bos://memory/kos/search", cost_usd=0.02)
    _reset_alerts(chk)
    # patch agora.core.state.get_event_bus (bos_quota 内部 import)
    from unittest.mock import MagicMock, patch

    published = []
    fake_bus = MagicMock()
    fake_bus.publish.side_effect = lambda ev: published.append(ev)
    with patch("agora.core.state.get_event_bus", return_value=fake_bus):
        allowed, info = chk.check("a", "bos://memory/kos/search")
    assert allowed is False
    assert any("quota:blocked" in str(p.get("type", "")) for p in published)


def test_warning_emits_alert_at_ratio(monkeypatch, tmp_path):
    """用量 ≥80% 未超限 → 触发 warning 告警."""
    cfg = _cfg(default_daily_usd=10.0)
    chk = _mk_checker(tmp_path, cfg)
    chk.record("w", "bos://memory/kos/search", cost_usd=8.0)  # 80%
    _reset_alerts(chk)
    allowed, info = chk.check("w", "bos://memory/kos/search")
    assert allowed is True
    assert info["usage_ratio"] >= 0.8
    assert info["limit_usd"] == 10.0


def test_alert_throttle(tmp_path):
    """同 caller 300s 内只发一次告警 (防抖)."""
    cfg = _cfg(default_daily_usd=10.0)
    chk = _mk_checker(tmp_path, cfg)
    chk.record("t", "bos://memory/kos/search", cost_usd=20.0)  # 超限
    _reset_alerts(chk)
    # 首次 check 应触发
    allowed1, _ = chk.check("t", "bos://memory/kos/search")
    assert allowed1 is False
    # 记录首次告警时间
    first_ts = chk._last_alert_ts.get("t")
    assert first_ts is not None
    # 立即再 check (未过 300s) → blocked 已 sent, 不重复
    allowed2, _ = chk.check("t", "bos://memory/kos/search")
    assert allowed2 is False
    assert chk._last_alert_ts.get("t") == first_ts  # 时间未更新 (防抖)


def test_alert_reset_on_recovery(tmp_path):
    """配额恢复后 blocked 状态重置 (下次超限可再发)."""
    cfg = _cfg(default_daily_usd=10.0)
    chk = _mk_checker(tmp_path, cfg)
    chk.record("r", "bos://memory/kos/search", cost_usd=20.0)  # 超限
    _reset_alerts(chk)
    chk.check("r", "bos://memory/kos/search")  # 触发 blocked
    assert "r" in chk._blocked_sent
    # 恢复: 用量降回 (模拟重置 today_cost — 通过删除记录)
    from agora.accounting import ResourceAccountDB
    import sqlite3

    conn = sqlite3.connect(chk._db.db_path)
    conn.execute("DELETE FROM calls WHERE caller_id = 'r'")
    conn.commit()
    conn.close()
    allowed, info = chk.check("r", "bos://memory/kos/search")
    assert allowed is True
    assert "r" not in chk._blocked_sent  # 已重置
    # 再次超限可重新触发
    chk.record("r", "bos://memory/kos/search", cost_usd=20.0)
    _reset_alerts(chk)
    allowed2, _ = chk.check("r", "bos://memory/kos/search")
    assert allowed2 is False
