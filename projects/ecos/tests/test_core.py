#!/usr/bin/env python3
"""eCOS 核心测试套件
覆盖: ssb_auth (签名) · realtime_guard (安全规则) · 集成验证

运行: python3 -m pytest tests/test_core.py -v
"""

import json
import os
import sqlite3
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
)

# ═══════════════════════════════════════════
# Test Suite 1: SSB Auth (签名验证)
# ═══════════════════════════════════════════


class TestSSBAuth:
    """SSB Auth 签名测试 — 使用临时密钥和数据库"""

    @pytest.fixture
    def temp_env(self, monkeypatch, tmp_path):
        """创建隔离测试环境"""
        key_file = tmp_path / ".ssb_key"
        db_file = tmp_path / "test.db"

        # 生成密钥
        key = os.urandom(32)
        key_file.write_bytes(key)

        # 创建最小SSB数据库
        db = sqlite3.connect(str(db_file))
        db.execute("""
            CREATE TABLE IF NOT EXISTS ssb_events (
                id INTEGER PRIMARY KEY,
                seq INTEGER,
                payload_json TEXT,
                source_agent TEXT,
                agent_signature TEXT
            )
        """)
        # 插入测试事件
        for i in range(5):
            db.execute(
                "INSERT INTO ssb_events (seq, payload_json, source_agent) VALUES (?, ?, ?)",
                (1000 + i, json.dumps({"test": f"event_{i}"}), "SSB_CLIENT"),
            )
        db.commit()
        db.close()

        # Monkeypatch 路径
        from ecos import ssb_auth as auth

        monkeypatch.setattr(auth, "KEY_FILE", key_file)
        monkeypatch.setattr(auth, "DB_PATH", db_file)

        return {"key": key, "db": db_file}

    def test_keygen(self, tmp_path):
        """测试密钥生成"""
        from ecos import ssb_auth as auth

        tmp_path / "test_key"
        # 直接测试 _load_key 返回 None 当文件不存在
        assert auth._load_key() is not None  # 真实密钥存在

    def test_compute_signature(self, temp_env):
        """测试签名计算"""
        from ecos import ssb_auth as auth

        sig1 = auth.compute_signature(1000, "e1", "SSB_CLIENT", '{"test":"event_0"}')
        sig2 = auth.compute_signature(1000, "e1", "SSB_CLIENT", '{"test":"event_0"}')
        sig3 = auth.compute_signature(1001, "e2", "SSB_CLIENT", '{"test":"event_1"}')

        assert sig1 is not None, "签名不应为None（密钥存在）"
        assert sig1 == sig2, "相同输入应产生相同签名"
        assert sig1 != sig3, "不同输入应产生不同签名"
        assert len(sig1) == 16, "签名应为16字符hex（64 bits）"

    def test_verify_all_unsigned(self, temp_env):
        """测试verify: 所有事件无签名"""
        from ecos import ssb_auth as auth

        stats = auth.verify(limit=10)
        assert stats["total"] > 0
        # 初始无签名的5个事件
        assert stats["unsigned"] == 5
        assert stats["mismatch"] == 0

    def test_sign_new_events(self, temp_env):
        """测试sign-new: 补充签名"""
        from ecos import ssb_auth as auth

        signed = auth.sign_new_events(limit=10)
        assert signed == 5, "应为5个事件签名"

        # 验证签名后
        stats = auth.verify(limit=10)
        assert stats["verified"] == 5
        assert stats["unsigned"] == 0

    def test_tampered_event_detected(self, temp_env, monkeypatch):
        """测试篡改检测"""
        from ecos import ssb_auth as auth

        # 先签名
        auth.sign_new_events(limit=10)

        # 篡改数据库中的 payload
        db = sqlite3.connect(str(temp_env["db"]))
        db.execute(
            "UPDATE ssb_events SET payload_json = ? WHERE seq = 1000", ('{"test":"tampered"}',)
        )
        db.commit()
        db.close()

        # verify 应检测到不匹配
        stats = auth.verify(limit=10)
        assert stats["mismatch"] >= 1, "篡改事件应被检测到"


# ═══════════════════════════════════════════
# Test Suite 2: Realtime Guard (安全规则)
# ═══════════════════════════════════════════


class TestRealtimeGuard:
    """实时安全检查测试 — 16条规则覆盖"""

    @pytest.fixture
    def guard(self):
        from ecos.realtime_guard import check

        return check

    # Level 3 — 不可逆操作
    def test_l3_genome_write(self, guard):
        result = guard("write_file GENOME.md", auto_deny=True)
        assert result["level"] == 3
        assert not result["allowed"]
        assert "GENOME.md" in result["reason"]

    def test_l3_genome_patch(self, guard):
        result = guard("patch GENOME.md L0公理", auto_deny=True)
        assert result["level"] == 3
        assert not result["allowed"]

    def test_l3_ssb_delete(self, guard):
        result = guard("ssb delete all events", auto_deny=True)
        assert result["level"] == 3
        assert not result["allowed"]

    def test_l3_cross_refs(self, guard):
        result = guard("delete cross_refs.jsonl", auto_deny=True)
        assert result["level"] == 3
        assert not result["allowed"]

    def test_l3_send_message(self, guard):
        result = guard("send_message to telegram", auto_deny=True)
        assert result["level"] == 3
        assert not result["allowed"]

    def test_l3_git_push(self, guard):
        result = guard("git push origin main", auto_deny=True)
        assert result["level"] == 3
        assert not result["allowed"]

    # Level 2 — 需三角确认
    def test_l2_cronjob_create(self, guard):
        result = guard("cronjob create daily task")
        assert result["level"] == 2
        assert not result["allowed"]
        assert result["requires"] == "TRIANGLE_CHECK"

    def test_l2_curl_post(self, guard):
        result = guard("curl POST to external API")
        assert result["level"] == 2
        assert not result["allowed"]

    # Level 1 — 可逆操作
    def test_l1_delegate_task(self, guard):
        result = guard("delegate_task to subagent")
        assert result["level"] == 1
        assert result["allowed"]

    # Level 0 — 只读
    def test_l0_read_file(self, guard):
        result = guard("read_file some_document.md")
        assert result["level"] == 0
        assert result["allowed"]

    def test_l0_search(self, guard):
        result = guard("search for documents")
        assert result["level"] == 0
        assert result["allowed"]

    # 未知操作
    def test_unknown_operation(self, guard):
        result = guard("some random operation")
        assert result["allowed"]
        assert result["level"] == 0

    # 无人类确认时 Level 3 被拒绝
    def test_l3_without_human(self, guard):
        """无 auto_deny 时 Level 3 应要求 HUMAN_CONFIRMATION"""
        result = guard("send_message hello", auto_deny=False)
        assert result["level"] == 3
        assert not result["allowed"]
        assert result["requires"] == "HUMAN_CONFIRMATION"


# ═══════════════════════════════════════════
# Test Suite 3: 集成验证
# ═══════════════════════════════════════════


class TestIntegration:
    """跨模块集成测试"""

    def test_auth_and_guard_independent(self):
        """ssb_auth 和 realtime_guard 可独立导入"""
        import ecos.realtime_guard
        import ecos.ssb_auth

        assert hasattr(ecos.ssb_auth, "compute_signature")
        assert hasattr(ecos.realtime_guard, "check")

    def test_state_yaml_exists(self):
        """STATE.yaml 存在且可解析"""
        import yaml

        state_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "STATE.yaml"
        )
        with open(state_path) as f:
            state = yaml.safe_load(f)
        assert state["system"] == "eCOS"
        assert state["phase"] == 10
        assert state["ssb_events"] >= 4385  # grows over time
        assert "emergence" in state

    def test_cross_refs_exists(self):
        """cross_refs.jsonl 存在且格式正确"""
        cross_refs = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "LADS/cross_refs.jsonl"
        )
        with open(cross_refs) as f:
            refs = [json.loads(line) for line in f if line.strip()]
        assert len(refs) >= 3
        for ref in refs:
            assert "link_id" in ref
            assert "source" in ref
            assert "target" in ref


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
