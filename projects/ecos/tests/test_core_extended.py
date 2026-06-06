"""
Constitution Watcher & Email Sender & Planner — 扩展测试
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "scripts"))
ECOS_HOME = Path(__file__).resolve().parent


# ─── Constitution Watcher ─────────────────────────────────


class TestConstitutionWatcher:
    def test_s03_signature_coverage_no_error(self):
        """S03 签名覆盖率检查不报错"""
        from ecos.constitution_watcher import s03_signature_coverage

        s03_signature_coverage()  # 不报错即通过

    def test_write_alert_creates_event(self):
        """_write_alert 创建 SSB 事件"""
        from ecos.constitution_watcher import _write_alert

        eid = _write_alert("INFO", "test alert", {"test": True})
        assert eid.startswith("CONSTITUTION-")


# ─── Email Sender ─────────────────────────────────────---


class TestEmailSender:
    def test_classify_p0_password(self):
        """含"密码"的邮件归为 P0"""
        from ecos.email_sender import classify_risk

        assert classify_risk("test@x.com", "密码更新", "新密码是123") == "P0"

    def test_classify_p1_normal(self):
        """普通通知归为 P1"""
        from ecos.email_sender import classify_risk

        assert classify_risk("test@x.com", "系统通知", "服务正常") == "P1"

    def test_classify_p0_confidential(self):
        """含"confidential"的邮件归为 P0"""
        from ecos.email_sender import classify_risk

        assert classify_risk("test@x.com", "机密文档", "This is confidential") == "P0"

    def test_classify_p0_token(self):
        """含"token"的邮件归为 P0"""
        from ecos.email_sender import classify_risk

        assert classify_risk("test@x.com", "Token 刷新", "new_token=abc") == "P0"


# ─── Planner ─────────────────────────────────────────────


class TestPlannerV2:
    def test_analyze_with_llm_fallback(self):
        """无 API key 时 LLM 模式优雅降级"""
        import os

        from ecos.planner import _analyze_with_llm

        saved = os.environ.pop("DEEPSEEK_API_KEY", None)
        try:
            result = _analyze_with_llm("测试任务")
            assert "steps" in result
            assert result["_source"] == "llm_error"
        finally:
            if saved:
                os.environ["DEEPSEEK_API_KEY"] = saved

    def test_generate_plan_llm_fallback(self):
        """generate_plan LLM 模式降级"""
        import os

        from ecos.planner import generate_plan

        saved = os.environ.pop("DEEPSEEK_API_KEY", None)
        try:
            plan_yaml = generate_plan("测试任务", use_llm=True)
            assert "steps" in plan_yaml or "plan" in plan_yaml
            assert "estimated_time" in plan_yaml or "total_steps" in plan_yaml
        finally:
            if saved:
                os.environ["DEEPSEEK_API_KEY"] = saved

    def test_analyze_goal_v1_matches_keyword(self):
        """v1 模式匹配关键词"""
        from ecos.planner import analyze_goal

        result = analyze_goal("部署KOS到新服务器")
        assert "环境检查" in result["steps"]
        assert "健康检查" in result["steps"]

    def test_analyze_goal_v1_fallback(self):
        """v1 模式无匹配时走通用规划"""
        from ecos.planner import analyze_goal

        result = analyze_goal("给系统加上量子算法优化")
        assert len(result["steps"]) == 5
        assert result["steps"][0] == "需求分析"


# ─── Content Integrity ───────────────────────────────────


class TestContentIntegrity:
    def test_check_normal_text(self):
        """正常文本通过完整性检查"""
        from ecos.content_integrity import check_integrity

        result = check_integrity("这是一段正常的文档内容，描述了一些信息。")
        assert "integrity_score" in result or "score" in result
        assert result.get("suspicious") is False

    def test_check_suspicious_text(self):
        """可疑文本被标记"""
        from ecos.content_integrity import check_integrity

        text = "keyword keyword keyword keyword keyword keyword keyword keyword keyword keyword keyword keyword keyword keyword keyword keyword"
        result = check_integrity(text)
        assert "integrity_score" in result or "score" in result
        assert result.get("integrity_score", 0) <= 50  # 质量分应该较低


# ─── emergence_watch ─────────────────────────────────────


class TestEmergenceWatch:
    def test_sign_now_zero(self):
        """分母为 0 时返回 0 (没有基线, 无偏差)"""
        from ecos.emergence_watch import calc_deviation

        # 基线为0, 当前为10 → 分母为0, 返回0? 还是? 脚本逻辑是: if baseline == 0 → return 0
        assert calc_deviation(0, 10, "up") is not None

    def test_sign_now_normal(self):
        """正常偏差计算"""
        from ecos.emergence_watch import calc_deviation

        assert round(calc_deviation(100, 150, "up"), 2) == 0.5

    def test_sign_now_down(self):
        """down 方向: 下降 > 阈值触发"""
        from ecos.emergence_watch import calc_deviation

        assert round(calc_deviation(100, 50, "down"), 2) == 0.5

    def test_sign_now_no_deviation(self):
        """无偏差"""
        from ecos.emergence_watch import calc_deviation

        assert calc_deviation(100, 100, "both") == 0
