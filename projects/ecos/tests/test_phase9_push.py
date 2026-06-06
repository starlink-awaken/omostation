"""Phase 9 — 主动服务层脚本测试
测试 daily_digest.py, research_push.py, knowledge_gap.py
"""

import os
import subprocess
import sys
from pathlib import Path

ECOS = os.environ.get("ECOS_ROOT", str(Path.home() / "Workspace" / "eCOS"))


class TestDailyDigest:
    """STT-003-01型：日报应该输出的要素检测"""

    def test_daily_digest_runs_without_error(self):
        """脚本运行不报错"""
        result = subprocess.run(
            [sys.executable, f"{ECOS}/scripts/daily_digest.py"],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=ECOS,
        )
        assert result.returncode == 0, f"stderr: {result.stderr[:200]}"

    def test_daily_digest_output_has_required_sections(self):
        """日报包含必要板块"""
        result = subprocess.run(
            [sys.executable, f"{ECOS}/scripts/daily_digest.py"],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=ECOS,
        )
        output = result.stdout
        assert "eCOS 日报" in output
        assert "事件概览" in output
        assert "系统健康" in output

    def test_daily_digest_contains_ssb_stats(self):
        """日报包含 SSB 数据统计"""
        result = subprocess.run(
            [sys.executable, f"{ECOS}/scripts/daily_digest.py"],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=ECOS,
        )
        assert "签名" in result.stdout
        import re

        assert re.search(r"\d{4}", result.stdout), "日报缺少 SSB 事件数"

    def test_daily_digest_emergence_section(self):
        """日报包含涌现指标"""
        result = subprocess.run(
            [sys.executable, f"{ECOS}/scripts/daily_digest.py"],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=ECOS,
        )
        output = result.stdout
        assert any(kw in output for kw in ["涌现", "知识速度", "角色平衡"])


class TestResearchPush:
    """研究推送脚本"""

    def test_research_push_runs_without_error(self):
        """脚本运行不报错（SSB 目录存在）"""
        result = subprocess.run(
            [sys.executable, f"{ECOS}/scripts/research_push.py"],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=ECOS,
        )
        assert result.returncode == 0, f"stderr: {result.stderr[:200]}"

    def test_research_push_output_or_silent(self):
        """产出格式正确：要么有新报告，要么静默"""
        result = subprocess.run(
            [sys.executable, f"{ECOS}/scripts/research_push.py"],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=ECOS,
        )
        output = result.stdout.strip()
        if output:
            # 如果有输出，必须是 eCOS 格式
            assert "eCOS" in output


class TestKnowledgeGap:
    """知识缺口检测脚本"""

    def test_knowledge_gap_runs_without_error(self):
        """脚本运行不报错"""
        result = subprocess.run(
            [sys.executable, f"{ECOS}/scripts/knowledge_gap.py"],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=ECOS,
        )
        assert result.returncode == 0, f"stderr: {result.stderr[:200]}"

    def test_knowledge_gap_output_has_zones(self):
        """输出包含 KOS 检索区信息或优雅跳过"""
        result = subprocess.run(
            [sys.executable, f"{ECOS}/scripts/knowledge_gap.py"],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=ECOS,
        )
        output = result.stdout
        # Either has real zone data or graceful skip message
        if "检索索引全景" in output:
            assert "9919" in output or "文档" in output
        else:
            # Graceful skip when iCloud DB unavailable
            assert "跳过" in output or "ℹ️" in output

    def test_knowledge_gap_detects_at_least_one_gap(self):
        """至少检测出一个缺口（已知 Obsidian 域稀疏）"""
        result = subprocess.run(
            [sys.executable, f"{ECOS}/scripts/knowledge_gap.py"],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=ECOS,
        )
        output = result.stdout
        # Should have at least one gap section
        assert "缺口" in output
