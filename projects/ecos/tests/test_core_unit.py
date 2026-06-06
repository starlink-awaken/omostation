"""
eCOS 核心单元测试 — 覆盖关键基础设施组件

运行: cd ~/Workspace/eCOS && python3 -m pytest tests/
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent / "scripts"))
ECOS_HOME = Path(__file__).resolve().parent


# ─── SSB Auth ─────────────────────────────────────────────────


class TestSsbAuth:
    def test_compute_signature_deterministic(self):
        """相同输入产生相同签名"""
        from ecos.ssb_auth import compute_signature

        s1 = compute_signature(1, "test-id", "agent", '{"key":"val"}')
        s2 = compute_signature(1, "test-id", "agent", '{"key":"val"}')
        assert s1 == s2
        assert s1 is not None

    def test_compute_signature_different_seq(self):
        """不同 seq 产生不同签名"""
        from ecos.ssb_auth import compute_signature

        s1 = compute_signature(1, "test-id", "agent", "{}")
        s2 = compute_signature(2, "test-id", "agent", "{}")
        assert s1 != s2

    def test_compute_signature_length(self):
        """签名长度为 16 字符 (64bits)"""
        from ecos.ssb_auth import compute_signature

        sig = compute_signature(1, "id", "agent", "")
        assert sig is None or len(sig) == 16


# ─── ecos_common ──────────────────────────────────────────────


class TestEcosCommon:
    def test_ecos_home_path(self):
        """ECOS_HOME 指向项目根目录"""
        from ecos.ecos_common import ECOS_HOME

        assert (ECOS_HOME / "GENOME.md").exists()

    def test_ssb_db_path(self):
        """SSB_DB_PATH 指向正确的数据库文件"""
        from ecos.ecos_common import SSB_DB_PATH

        assert str(SSB_DB_PATH).endswith("ecos.db")

    def test_now_iso_format(self):
        """now_iso() 返回合法 ISO 格式"""
        from ecos.ecos_common import now_iso

        ts = now_iso()
        assert "T" in ts
        assert ts.endswith("+08:00") or "+00:00" in ts

    def test_get_conn(self):
        """get_conn() 返回可工作的数据库连接"""
        from ecos.ecos_common import get_conn

        conn = get_conn()
        assert conn is not None
        conn.execute("SELECT 1")
        conn.close()


# ─── ecos_timeout ────────────────────────────────────────────


class TestEcosTimeout:
    def test_timeout_normal(self):
        """正常函数不超时"""
        from ecos.ecos_timeout import timeout

        @timeout(5)
        def fast():
            return 42

        assert fast() == 42

    def test_timeout_triggers(self):
        """超时函数抛出 TimeoutError"""
        import time

        from ecos.ecos_timeout import TimeoutError, timeout

        @timeout(1)
        def slow():
            time.sleep(5)
            return 0

        with pytest.raises(TimeoutError):
            slow()

    def test_retry_success(self):
        """重试装饰器：第二次尝试成功"""
        from ecos.ecos_timeout import retry

        call_count = [0]

        @retry(max_attempts=3, delay=0)
        def flaky():
            call_count[0] += 1
            if call_count[0] < 2:
                raise ValueError("not yet")
            return "ok"

        assert flaky() == "ok"
        assert call_count[0] == 2


# ─── Model Balancer ─────────────────────────────────────────


class TestModelBalancer:
    def test_get_model_usage_no_error(self):
        """model_balancer 读取无异常"""
        from ecos.model_balancer import get_model_usage

        models, imbalance = get_model_usage(stats=True)
        assert "DeepSeek" in models
        assert isinstance(imbalance, (int, float))

    def test_recommend_returns_string(self):
        """推荐返回模型名"""
        from ecos.model_balancer import recommend

        model = recommend("reasoning")
        assert isinstance(model, str)
        assert len(model) > 0


# ─── Planner ────────────────────────────────────────────────


class TestPlanner:
    def test_available_wf(self):
        """列出可用 Workflow"""
        from ecos.planner import list_available_wfs

        wfs = list_available_wfs()
        assert len(wfs) >= 8  # 至少 8 个 WF
        assert any("WF-001" in w["id"] for w in wfs)

    def test_analyze_goal(self):
        """目标分析返回步骤"""
        from ecos.planner import analyze_goal

        result = analyze_goal("修复审计发现的问题")
        assert "steps" in result
        assert len(result["steps"]) > 0
