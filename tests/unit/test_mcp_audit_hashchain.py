"""P2-2: audit hashchain 防篡改测试.

覆盖:
- 链连续性: 写入多条事件后 verify_chain ok
- 篡改检测: 修改已写行后 verify_chain 报 hash mismatch
- 链断裂检测: 删除中间行后 prev 不连续报 chain break
- 旧数据/锚点容忍: prev_hash='GENESIS'/'' 的行跳过匹配
- 清理边界: 首行 prev_hash 重置为 GENESIS 后 verify 通过
"""

from __future__ import annotations

import sqlite3

import pytest

from agora.server.mcp import AuditSubscriber


class _FakeBus:
    def register_hook(self, fn):
        self._hook = fn

    def emit(self, event):
        self._hook(event)


def _make_auditor(tmp_path):
    bus = _FakeBus()
    auditor = AuditSubscriber(bus, db_path=str(tmp_path / "audit.db"))
    bus.register_hook(auditor.on_event)  # 显式注册 (真实场景在 mcp.py:529 模块级注册)
    return bus, auditor


def _emit(bus, auditor, event_type="registry:service.registered", n=1):
    for i in range(n):
        bus.emit(
            {
                "type": event_type,
                "id": f"evt-{i}",
                "source": "test",
                "payload": {"svc": f"svc-{i}", "_duration_ms": 1.0},
            }
        )
    return auditor


def test_chain_continuous_ok(tmp_path):
    """连续写入多条, verify_chain 应 ok."""
    bus, auditor = _make_auditor(tmp_path)
    _emit(bus, auditor, n=5)
    result = auditor.verify_chain()
    assert result["ok"] is True
    assert result["total"] == 5
    assert result["verified"] >= 5


def test_tamper_detected(tmp_path):
    """篡改已写行 payload, verify_chain 应报 hash mismatch."""
    bus, auditor = _make_auditor(tmp_path)
    _emit(bus, auditor, n=3)
    conn = sqlite3.connect(str(tmp_path / "audit.db"))
    conn.execute("UPDATE audit_log SET actor = 'hacked' WHERE id = 'evt-1'")
    conn.commit()
    conn.close()
    result = auditor.verify_chain()
    assert result["ok"] is False
    assert any("mismatch" in e for e in result["errors"])


def test_chain_break_detected(tmp_path):
    """删除中间行, prev 不连续应报 chain break."""
    bus, auditor = _make_auditor(tmp_path)
    _emit(bus, auditor, n=4)
    conn = sqlite3.connect(str(tmp_path / "audit.db"))
    conn.execute("DELETE FROM audit_log WHERE id = 'evt-2'")
    conn.commit()
    conn.close()
    result = auditor.verify_chain()
    assert result["ok"] is False
    assert any("chain break" in e for e in result["errors"])


def test_genesis_anchor_tolerated(tmp_path):
    """prev_hash='GENESIS' 的行作为锚点, verify 应跳过匹配通过."""
    bus, auditor = _make_auditor(tmp_path)
    _emit(bus, auditor, n=3)
    conn = sqlite3.connect(str(tmp_path / "audit.db"))
    # 模拟清理边界: 重写首行 prev_hash 为 GENESIS
    conn.execute("UPDATE audit_log SET prev_hash = 'GENESIS' WHERE id = 'evt-1'")
    conn.commit()
    conn.close()
    result = auditor.verify_chain()
    assert result["ok"] is True


def test_old_rows_tolerated(tmp_path):
    """旧数据 (prev_hash='') 视为锚点, verify 应通过."""
    bus, auditor = _make_auditor(tmp_path)
    _emit(bus, auditor, n=2)
    conn = sqlite3.connect(str(tmp_path / "audit.db"))
    conn.execute("UPDATE audit_log SET prev_hash = '' WHERE id = 'evt-0'")
    conn.commit()
    conn.close()
    result = auditor.verify_chain()
    assert result["ok"] is True


def test_cleanup_boundary(tmp_path):
    """清理删除旧行后, 新首行 prev_hash 重置为 GENESIS, verify 通过."""
    bus, auditor = _make_auditor(tmp_path)
    _emit(bus, auditor, n=4)
    conn = sqlite3.connect(str(tmp_path / "audit.db"))
    # 模拟 >30 天清理删除了 evt-0/evt-1 (链中间), 重写新首行锚点
    conn.execute("DELETE FROM audit_log WHERE id IN ('evt-0','evt-1')")
    conn.execute(
        "UPDATE audit_log SET prev_hash = 'GENESIS' "
        "WHERE rowid = (SELECT rowid FROM audit_log ORDER BY rowid ASC LIMIT 1)"
    )
    conn.commit()
    conn.close()
    result = auditor.verify_chain()
    assert result["ok"] is True
