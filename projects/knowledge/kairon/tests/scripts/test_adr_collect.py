"""P28-W1-ADR-COLLECT — 单元测试.

目标:
  - 验证关键词解析、源扫描、置信度评分、markdown 渲染
  - 用 tmp_path 模拟工作区布局, 避免污染真实仓库
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# 把 scripts 目录加进 sys.path, 让 `import adr_collect` 可用
SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import adr_collect as ac  # type: ignore[reportMissingImports]

# ── 公共 fixture ──────────────────────────────────────────────


@pytest.fixture
def fake_workspace(tmp_path: Path) -> Path:
    """构造一个最小化工作区布局, 用于单元测试."""
    ws = tmp_path
    # governance_plan.md
    (ws / "projects/kairon/docs").mkdir(parents=True)
    (ws / "projects/kairon/docs/governance_plan.md").write_text(
        "# Kairon Remediation Roadmap\n\n"
        "## P0: Restore Trustworthiness\n\n"
        "### 1. Rebuild inventory and fix repo-facing docs\n\n"
        "- **Problem**: docs claim 26/31 packages, repo has 25\n"
        "- **Verification**: package count script returns 25\n",
        encoding="utf-8",
    )
    # architecture_audit.md
    (ws / "projects/kairon/docs/architecture_audit.md").write_text(
        "# Kairon Architecture Audit v2\n\n"
        "## P0\n\n- Inventory drift\n- packages/ boundary pollution\n\n"
        "## P1\n\n- Unclear operator home\n",
        encoding="utf-8",
    )
    # tool-heatmap-phase28.md
    (ws / ".omo/_knowledge/management").mkdir(parents=True)
    (ws / ".omo/_knowledge/management/tool-heatmap-phase28.md").write_text(
        "# 工具使用热力图 — Phase 28 基线审计\n\n"
        "## 四、关键结论\n\n"
        "### 结论 1：G27.1 KPI 未落地\n"
        "agora 路由表仅 2 条, 25 个包中只有 eidos 注册。\n\n"
        "### 结论 2：技术情报雷达的实现路径更清晰了\n"
        "场景 B 不依赖 agora 网关正常运行。\n",
        encoding="utf-8",
    )
    # pkg-slim-plan.md
    (ws / ".omo/_delivery").mkdir(parents=True)
    (ws / ".omo/_delivery/phase28-pkg-slim-plan.md").write_text(
        "# P28-W2-PKG-SLIM 瘦身计划\n\n"
        "## 二、立即归档(本期执行)\n\n"
        "### 2.1 kairon-assistant\n"
        "0 外部 import、孤儿包。\n\n"
        "### 2.2 kairon-voice\n"
        "0 外部 import、whisper 缺依赖。\n",
        encoding="utf-8",
    )
    return ws


# ── 单元测试 ──────────────────────────────────────────────────


class TestConfidenceScoring:
    def test_confidence_scoring_high_source(self) -> None:
        """源包含 file:line → HIGH."""
        score = ac.score_confidence("docs/governance_plan.md:42", has_keyword_match=True)
        assert score == "HIGH"

    def test_confidence_scoring_low_source(self) -> None:
        """源仅命中决策关键词, 无任何源定位 → LOW."""
        score = ac.score_confidence("decision", has_keyword_match=True)
        assert score == "LOW"

    def test_confidence_scoring_commit_hash(self) -> None:
        """源包含 commit hash(无文件定位)→ MED."""
        score = ac.score_confidence("git:abc123def456", has_keyword_match=True)
        assert score == "MED"

    def test_confidence_scoring_file_only(self) -> None:
        """源是文档路径(无行号)→ MED."""
        score = ac.score_confidence("docs/governance_plan.md", has_keyword_match=True)
        assert score == "MED"


class TestFormatCandidate:
    def test_format_candidate_markdown_includes_all_fields(self) -> None:
        """ADRCandidate.to_markdown 包含所有必需字段."""
        c = ac.ADRCandidate(
            title="测试 ADR 标题",
            source="docs/test.md:10",
            date_proposed="2026-06-05",
            status="PROPOSED",
            context="上下文内容",
            decision="决策内容",
            consequences="影响范围",
            tags=["#test", "#adr"],
            confidence="HIGH",
            candidate_id="001",
        )
        md = c.to_markdown()
        # 必备字段
        assert "## ADR-001: 测试 ADR 标题" in md
        assert "**Source**: docs/test.md:10" in md
        assert "**Date proposed**: 2026-06-05" in md
        assert "**Status**: PROPOSED" in md
        assert "**Context**: 上下文内容" in md
        assert "**Decision**: 决策内容" in md
        assert "**Consequences**: 影响范围" in md
        assert "**Tags**: #test #adr" in md
        assert "**Confidence**: HIGH" in md


class TestMarkdownExtraction:
    def test_extract_decision_from_markdown_section(self) -> None:
        """extract_section_text 能从 markdown 中找到匹配标题的正文."""
        text = "# Top\n\n## P0 Section\n\n正文内容 A\n正文内容 B\n\n## P1 Section\n\n其他内容\n"
        result = ac.extract_section_text(text, "P0 Section")
        assert result is not None
        assert "正文内容 A" in result
        assert "正文内容 B" in result
        assert "其他内容" not in result

    def test_extract_decision_lines_finds_keyword(self) -> None:
        """extract_decision_lines 能找出命中决策关键词的行."""
        text = "普通行 1\n## 决策: 采用 agora 路由\n普通行 2\nWe decide to migrate to llm-gateway\n"
        hits = ac.extract_decision_lines(text)
        assert len(hits) >= 2
        # 至少包含中文与英文关键词命中
        all_text = " ".join(line for _, line in hits)
        assert "决策" in all_text or "采用" in all_text
        assert "decide" in all_text or "migrate" in all_text


class TestCommitParsing:
    def test_parse_commit_message_extracts_decision_keyword(self) -> None:
        """git commit 行解析 + 关键词识别."""
        # 模拟 git log 输出
        fake_log = (
            "abc123def456|2026-06-05 10:00:00 +0800|feat: migrate to llm-gateway\n"
            "def456abc789|2026-06-04 09:00:00 +0800|docs: update README\n"
            "9876543210ab|2026-06-03 08:00:00 +0800|chore: deprecate old API\n"
        )
        # 用 monkeypatch 替换 subprocess.run
        import subprocess

        class FakeResult:
            stdout = fake_log
            returncode = 0

        def fake_run(*args, **kwargs):
            return FakeResult()

        with patch.object(subprocess, "run", side_effect=fake_run):
            workspace = Path("/tmp")
            candidates = ac.scan_recent_commits(workspace, days=30)

        # migrate / deprecate 命中, docs 不命中
        assert len(candidates) == 2
        titles = [c.title for c in candidates]
        assert any("migrate" in t.lower() for t in titles)
        assert any("deprecate" in t.lower() for t in titles)
        assert not any("update README" in t.lower() for t in titles)
        # 至少 1 个的 confidence 是 MED(commit hash)
        assert any(c.confidence == "MED" for c in candidates)


class TestSourceScanners:
    def test_scan_finds_governance_decision(self, fake_workspace: Path) -> None:
        """scan_governance_plan 能从 governance_plan.md 找到 P0 决策."""
        candidates = ac.scan_governance_plan(fake_workspace)
        assert len(candidates) >= 1
        # 标题应包含治理决策关键词
        assert any("Rebuild inventory" in c.title for c in candidates)
        # 源定位应包含 file:line
        assert all(":" in c.source and c.source.count(":") == 1 for c in candidates if c.confidence == "HIGH")
        # 状态应为 PROPOSED
        assert all(c.status == "PROPOSED" for c in candidates)

    def test_scan_finds_architecture_audit_p_levels(self, fake_workspace: Path) -> None:
        """scan_architecture_audit 抓取 P0/P1/P2 段."""
        candidates = ac.scan_architecture_audit(fake_workspace)
        # 至少抓到 P0 与 P1
        assert len(candidates) >= 2
        tags = {tuple(c.tags) for c in candidates}
        # 至少一个 P0, 一个 P1
        assert any("#risk-p0" in t for t in tags)
        assert any("#risk-p1" in t for t in tags)

    def test_scan_finds_tool_heatmap_conclusions(self, fake_workspace: Path) -> None:
        """scan_tool_heatmap 抓取结论 1 / 结论 2."""
        candidates = ac.scan_tool_heatmap(fake_workspace)
        assert len(candidates) >= 2
        # 全部带 #agora 标签
        assert all("#agora" in c.tags for c in candidates)

    def test_scan_finds_pkg_slim_archive_decisions(self, fake_workspace: Path) -> None:
        """scan_pkg_slim_plan 抓取 2.1/2.2 立即归档项."""
        candidates = ac.scan_pkg_slim_plan(fake_workspace)
        assert len(candidates) == 2
        titles = " ".join(c.title for c in candidates)
        assert "kairon-assistant" in titles
        assert "kairon-voice" in titles

    def test_scan_handles_missing_source_gracefully(self, tmp_path: Path) -> None:
        """源文件不存在时, scanner 返回空列表, 不抛异常."""
        # 构造空 workspace(无任何源文件)
        empty = tmp_path / "empty_workspace"
        empty.mkdir()
        assert ac.scan_governance_plan(empty) == []
        assert ac.scan_architecture_audit(empty) == []
        assert ac.scan_tool_heatmap(empty) == []
        assert ac.scan_pkg_slim_plan(empty) == []


class TestReportBuilding:
    def test_build_report_includes_all_sections(self, fake_workspace: Path) -> None:
        """build_report 生成的报告包含所有 section."""
        candidates = (
            ac.scan_governance_plan(fake_workspace)
            + ac.scan_architecture_audit(fake_workspace)
            + ac.scan_tool_heatmap(fake_workspace)
            + ac.scan_pkg_slim_plan(fake_workspace)
        )
        sources = [
            "projects/kairon/docs/governance_plan.md",
            "projects/kairon/docs/architecture_audit.md",
            ".omo/_knowledge/management/tool-heatmap-phase28.md",
            ".omo/_delivery/phase28-pkg-slim-plan.md",
        ]
        report = ac.build_report(candidates, Path("/tmp/out.md"), sources)
        # 必备 section
        assert "# Phase 28 — ADR 候选收集报告" in report
        assert "## 0. 扫描源清单" in report
        assert "## 1. 候选 ADR 列表" in report
        assert "## 2. 已废弃候选" in report
        assert "## 3. W3 阶段建议" in report
        # 至少 2 个 ADR 候选
        assert "## ADR-" in report
        # 报告内候选数 ≥ 2
        adr_count = report.count("## ADR-")
        assert adr_count >= 2


class TestCLI:
    def test_main_scan_runs_successfully(self, fake_workspace: Path, tmp_path: Path, capsys) -> None:
        """CLI scan 子命令能跑通, 输出包含关键摘要."""
        out = tmp_path / "report.md"
        rc = ac.main(
            [
                "scan",
                "--workspace",
                str(fake_workspace),
                "--output",
                str(out),
                "--days",
                "30",
            ]
        )
        captured = capsys.readouterr()
        assert rc == 0
        assert "扫描 workspace" in captured.out
        assert "候选总数" in captured.out
        assert out.exists()
        text = out.read_text(encoding="utf-8")
        # 报告含至少 1 个 ADR
        assert "## ADR-" in text

    def test_main_help_exits_cleanly(self, capsys) -> None:
        """CLI --help 正常退出."""
        with pytest.raises(SystemExit) as exc:
            ac.main(["--help"])
        assert exc.value.code == 0
