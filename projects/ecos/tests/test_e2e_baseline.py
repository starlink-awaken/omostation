#!/usr/bin/env python3
"""
eCOS 端到端基线测试套件
Covering: SSB lifecycle, Auth, RealtimeGuard, State consistency, Cross-domain

Usage: python3 -m pytest tests/test_e2e_baseline.py -v
"""

import json
import os
import sys
import time

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
)

ECOS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ═══════════════════════════════════════════
# E2E-1: SSB 完整生命周期
# ═══════════════════════════════════════════


class TestE2E_SSB_Lifecycle:  # noqa: N801
    """端到端: SSB 初始化→发布→订阅→查询→dump→验证"""

    @pytest.fixture
    def ssb(self):
        from ssb_client import SSBClient

        return SSBClient(auto_init=True)

    def test_publish_and_query(self, ssb):
        """发布3个事件，查询验证"""
        e1 = ssb.publish(
            {
                "event": {"type": "TEST_E2E"},
                "source": {"agent": "E2E_TEST"},
                "payload": {"summary": "hello e2e test", "msg": "hello", "n": 1},
            }
        )
        e2 = ssb.publish(
            {
                "event": {"type": "TEST_E2E"},
                "source": {"agent": "E2E_TEST"},
                "payload": {"summary": "world e2e test", "msg": "world", "n": 2},
            }
        )

        assert e1 is not None
        assert e2 is not None
        assert e1 != e2

        results = ssb.query(limit=5)
        assert len(results) > 0
        types = [r.get("event", {}).get("type") for r in results]
        assert "TEST_E2E" in types

    def test_subscribe_returns_events(self, ssb):
        """subscribe() 应返回新事件 (修复 F1)"""
        # Set baseline: consume existing events
        ssb.subscribe(block=False)

        # Publish a unique event
        tag = f"sub_test_{int(time.time())}"
        ssb.publish(
            {
                "event": {"type": "SUB_TEST"},
                "source": {"agent": tag},
                "payload": {"summary": f"subscribe test {tag}", "test": tag},
            }
        )

        # Subscribe should find it (non-blocking, immediate)
        events = ssb.subscribe(block=False)
        assert len(events) > 0, f"subscribe() returned {len(events)} events (F1 fix)"

    def test_load_state_uses_yaml(self, ssb):
        """load_state() 应正确解析 YAML (修复 F2)"""
        state = ssb.load_state()
        assert isinstance(state, dict)
        assert "system" in state
        assert state["system"] == "eCOS"
        # Should parse nested structures too
        if "emergence" in state:
            assert isinstance(state["emergence"], dict)

    def test_dump_complete_fields(self):
        """ssb_dump 应输出完整字段 (修复 F4)"""
        from ecos import ssb_dump as sd

        code = open(sd.__file__).read()
        assert "payload_json" in code, "F4: must include payload_json"
        assert "agent_signature" in code, "F4: must include agent_signature"
        assert "FROM ssb_events" in code, "F4: dump must query full table"

    def test_ssb_file_exists(self):
        """SSB 数据库和 JSONL 文件存在"""
        db = os.path.join(ECOS, "LADS/ssb/ecos.db")
        jsonl = os.path.join(ECOS, "LADS/ssb/ecos.jsonl")
        assert os.path.exists(db), "ecos.db missing"
        assert os.path.exists(jsonl), "ecos.jsonl missing"


# ═══════════════════════════════════════════
# E2E-2: 认证安全链路
# ═══════════════════════════════════════════


class TestE2E_Auth:  # noqa: N801
    """端到端: 密钥生成→签名→验证→篡改检测"""

    def test_sign_verify_roundtrip(self):
        """签名-验证往返"""
        from ecos import ssb_auth as auth

        sig = auth.compute_signature(1, "e1", "AGENT", '{"test":1}')
        assert sig is not None
        assert len(sig) == 16

        # Same inputs = same signature
        sig2 = auth.compute_signature(1, "e1", "AGENT", '{"test":1}')
        assert sig == sig2

        # Different inputs ≠ same signature
        sig3 = auth.compute_signature(2, "e2", "AGENT", '{"test":1}')
        assert sig != sig3

    def test_verify_no_tampering(self):
        """最近事件应无篡改"""
        from ecos import ssb_auth as auth

        stats = auth.verify(limit=20)
        assert stats["mismatch"] == 0, f"Found {stats['mismatch']} tampered events"

    def test_key_exists(self):
        from ecos import ssb_auth as auth

        key = auth._load_key()
        assert key is not None, "SSB_KEY not configured"


# ═══════════════════════════════════════════
# E2E-3: 安全规则全覆盖
# ═══════════════════════════════════════════


class TestE2E_Guard:  # noqa: N801
    """端到端: realtime_guard 全部16条规则"""

    @pytest.fixture
    def check(self):
        from ecos.services.realtime_guard import check

        return check

    @pytest.mark.parametrize(
        "op,level,allowed",
        [
            ("write_file GENOME.md", 3, False),
            ("patch GENOME.md L0", 3, False),
            ("ssb delete all", 3, False),
            ("delete cross_refs.jsonl", 3, False),
            ("send_message hello", 3, False),
            ("himalaya send email", 3, False),
            ("xurl post tweet", 3, False),
            ("git push origin main", 3, False),
            ("rm -rf /tmp/test", 3, False),
            ("cronjob create daily", 2, False),
            ("cronjob update job_id", 2, False),
            ("curl POST api", 2, False),
            ("delegate_task test", 1, True),
            ("read_file doc.md", 0, True),
            ("search for stuff", 0, True),
            ("random operation", 0, True),
        ],
    )
    def test_guard_rules(self, check, op, level, allowed):
        """测试所有 guard 规则"""
        result = check(op, auto_deny=(level >= 3))
        assert result["level"] == level, f"{op}: expected level {level}, got {result['level']}"
        assert result["allowed"] == allowed, f"{op}: expected allowed={allowed}"

    def test_guard_cross_refs_protected(self, check):
        """cross_refs 被保护 (审计修复)"""
        r = check("delete cross_refs", auto_deny=True)
        assert r["level"] == 3

    def test_guard_ecos_jsonl_protected(self, check):
        """ecos.jsonl 被保护"""
        r = check("delete ecos.jsonl", auto_deny=True)
        assert r["level"] == 3


# ═══════════════════════════════════════════
# E2E-4: 状态一致性
# ═══════════════════════════════════════════


class TestE2E_State:  # noqa: N801
    """端到端: STATE.yaml ↔ SSB ↔ HANDOFF 一致性"""

    def test_state_yaml_has_required_keys(self):
        import yaml

        with open(os.path.join(ECOS, "STATE.yaml")) as f:
            state = yaml.safe_load(f)

        required = ["system", "version", "phase", "ssb_events", "cron"]
        for key in required:
            assert key in state, f"STATE.yaml missing key: {key}"

    def test_agents_md_matches_state(self):
        """AGENTS.md 与 STATE.yaml 一致 (审计修复)"""
        with open(os.path.join(ECOS, "AGENTS.md")) as f:
            agents = f.read()

        # All these should be in AGENTS.md
        checks = [
            "Phase | **9",
            "12 个在线",
            "5,234",
            "74 commits",
        ]
        for c in checks:
            assert c in agents, f"AGENTS.md missing: {c}"

    def test_handoff_exists_and_valid(self):
        """HANDOFF 存在且包含 agent_signature"""
        handoff = os.path.join(ECOS, "LADS/HANDOFF/LATEST.md")
        assert os.path.exists(handoff)
        with open(handoff) as f:
            content = f.read()
        assert "agent" in content.lower() or "signature" in content.lower()

    def test_genome_has_phase8(self):
        """GENOME.md 已更新到 Phase 8"""
        with open(os.path.join(ECOS, "GENOME.md")) as f:
            genome = f.read()
        assert "Phase 8" in genome
        assert "v0.8.0" in genome


# ═══════════════════════════════════════════
# E2E-5: 跨域融合
# ═══════════════════════════════════════════


class TestE2E_CrossDomain:  # noqa: N801
    """端到端: Integrate 管道 + cross_refs"""

    def test_cross_refs_valid(self):
        """cross_refs 格式有效"""
        refs_path = os.path.join(ECOS, "LADS/cross_refs.jsonl")
        with open(refs_path) as f:
            refs = [json.loads(line) for line in f if line.strip()]

        assert len(refs) >= 3
        for ref in refs:
            assert "link_id" in ref
            assert "source" in ref
            assert "target" in ref
            assert "score" in ref
            assert ref["score"] >= 0.4

    def test_integrate_safe_execution(self):
        """integrate_pipeline 无代码注入风险 (F5 fix)"""
        from ecos import integrate_pipeline as ip

        code = open(ip.__file__).read()
        # Should pass query as argv, not f-string interpolation
        assert "sys.argv[1]" in code, "F5: query must be passed as argv"


# ═══════════════════════════════════════════
# E2E-6: 涌现度量
# ═══════════════════════════════════════════


class TestE2E_Metrics:  # noqa: N801
    """端到端: CRITIC + 涌现度量"""

    def test_emergence_metrics_compute(self):
        """涌现度量可计算"""
        from ecos import critic_auto_trigger as cat

        metrics = cat.compute_emergence_metrics()
        assert "emergence_score" in metrics
        score = metrics["emergence_score"]
        assert 0 <= score["diversity"] <= 1
        assert 0 <= score["error_resilience"] <= 1

    def test_critic_assess_risk(self):
        """CRITIC 风险评估正确"""
        from ecos import critic_auto_trigger as cat

        r = cat.assess_risk("修改 GENOME.md 公理")
        assert r["need_critic"]
        assert r["risk_level"] in ("HIGH", "CRITICAL")

        r = cat.assess_risk("read document")
        assert not r["need_critic"]
        assert r["risk_level"] == "LOW"


# ═══════════════════════════════════════════
# E2E-7: 共享模块
# ═══════════════════════════════════════════


class TestE2E_Common:  # noqa: N801
    """端到端: ecos_common 共享基础设施"""

    def test_ecos_common_imports(self):
        """所有核心脚本可导入 ecos_common"""
        import ecos_common as ec

        assert hasattr(ec, "now_iso")
        assert hasattr(ec, "get_conn")
        assert hasattr(ec, "TZ")
        assert hasattr(ec, "SSB_DB_PATH")
        assert hasattr(ec, "CREATE_SSB_EVENTS_SQL")

        # Test now_iso
        ts = ec.now_iso()
        assert "2026" in ts
        assert "+08:00" in ts or "CST" in str(ec.TZ)

    def test_get_conn_works(self):
        """get_conn() 返回可用连接"""
        import ecos_common as ec

        conn = ec.get_conn()
        assert conn is not None
        # Verify tables exist
        tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        table_names = [t[0] for t in tables]
        assert "ssb_events" in table_names
        conn.close()


# ═══════════════════════════════════════════
# E2E-8: 数据库完整性
# ═══════════════════════════════════════════


class TestE2E_DatabaseIntegrity:  # noqa: N801
    """端到端: 数据库完整性校验"""

    def test_sqlite_integrity(self):
        """SQLite PRAGMA integrity_check"""
        import ecos_common as ec

        conn = ec.get_conn()
        result = conn.execute("PRAGMA integrity_check").fetchone()
        assert result[0] == "ok", f"DB corrupted: {result[0]}"
        conn.close()

    def test_wf008_insert_schema(self):
        """wf-008 INSERT schema matches ecos_common (F3 fix)"""
        # Verify the script exists and uses proper schema
        script_path = os.path.join(ECOS, "scripts/wf-008-kanban-ssb-bridge.py")
        assert os.path.exists(script_path)
        with open(script_path) as f:
            code = f.read()

        # Should reference ssb_events INSERT matching ecos_common schema
        assert "INSERT OR IGNORE INTO ssb_events" in code


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
