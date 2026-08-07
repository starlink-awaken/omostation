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
