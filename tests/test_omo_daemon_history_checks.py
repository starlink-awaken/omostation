"""Regression: omo_daemon.run_once 必须把 audit checks 写入 governance-history.

ADR-0390 根因: 8 月起 omo_daemon.run_once() 的 append_entry 调用漏写
`checks` 字段, 导致 gate-effectiveness / gate-roi-report 从 8 月起失明
(governance-history.jsonl 中无 checks 数组 → 7 个 gate 全部 0 fires →
被误判为 PRUNE/RETIRE). 此测试确保 run_once 写出的 record 含完整 checks.

检查字段: name (str) / category (str) / score (number) / severity ∈ {ok,warn,fail}.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

OMO_SRC = Path(__file__).resolve().parents[1] / "src"
if str(OMO_SRC) not in sys.path:
    sys.path.insert(0, str(OMO_SRC))


def test_run_once_appends_checks_to_history(tmp_path, monkeypatch):
    """run_once 成功 audit 时, append_entry payload 必须含 checks 列表."""
    # 1) 准备隔离的 history_path 与跳开 agora 探活 (CI 环境友好)
    history_path = tmp_path / "governance-history.jsonl"
    monkeypatch.setenv("OMO_AUDIT_SKIP_AGORA", "1")

    # 2) 调用 run_once, history_path 透传
    from omo.omo_daemon import run_once

    result = run_once(history_path=history_path, auto_consume=False)

    # 3) audit 失败也不应崩 (CI fresh checkout 时 audit 偶尔失败是允许的)
    #    但若 history_appended=True, 则 record 必须有 checks
    if not result.history_appended:
        import pytest
        pytest.skip("audit 未产出 report, 跳过 daemon append 验证")

    # 4) 读回最后一条 record, 验证 checks 字段存在且完整
    records = [
        json.loads(line_)
        for line_ in history_path.read_text(encoding="utf-8").splitlines()
        if line_.strip()
    ]
    assert records, "history 文件应为非空"
    last = records[-1]
    assert "checks" in last, (
        f"daemon append 漏写 checks (ADR-0390 根因): keys={list(last.keys())}"
    )
    checks = last["checks"]
    assert isinstance(checks, list)
    assert len(checks) >= 1, "daemon append 必须含至少 1 个 check 记录"
    # 5) 每个 check 字段 schema 校验 (与 omo_audit.format 一致)
    for c in checks:
        assert isinstance(c.get("name"), str) and c["name"]
        assert isinstance(c.get("category"), str)
        assert isinstance(c.get("score"), (int, float))
        assert c.get("severity") in {"ok", "warn", "fail"}
    # 6) source 必须标识 omo_daemon (与 omo_audit governance_history_main 兼容)
    assert last.get("source") == "omo_daemon"


def test_daemon_history_appended_flag_honors_audit_failure():
    """若 audit 失败, history_appended 必须为 False (不写空 record)."""
    from omo.omo_daemon import run_once

    # 强制 audit 抛异常: monkeypatch run_governance_audit via sys.modules stub
    import omo.omo_daemon as mod

    orig = mod.run_governance_audit if hasattr(mod, "run_governance_audit") else None

    def boom(*_a, **_k):
        raise RuntimeError("simulated audit failure")

    try:
        mod.run_governance_audit = boom
        result = run_once(history_path=None, auto_consume=False)
    finally:
        if orig is not None:
            mod.run_governance_audit = orig
    assert result.audit_score is None
    assert result.history_appended is False