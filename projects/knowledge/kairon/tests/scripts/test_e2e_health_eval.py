"""P29-W0-E2E-EVAL — 单元测试.

目标:
  - DraftStructure 解析覆盖 3 节齐全/缺节/引用计数
  - RecallMetrics 计算与等级阈值
  - warn_lines 输出内容正确
  - CLI 干跑(临时 draft 文件)
"""

from __future__ import annotations

from pathlib import Path

import pytest

# 把 scripts 目录加进 sys.path, 让 `import e2e_health_eval` 可用
SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
import sys

sys.path.insert(0, str(SCRIPTS_DIR))

import e2e_health_eval as ev  # type: ignore[reportMissingImports]

# ── DraftStructure ─────────────────────────────────────────


def test_parse_draft_structure_complete() -> None:
    md = (
        "# 报告\n"
        "## 问题摘要\n问题背景描述 [1] [2] [3].\n\n"
        "## 政策依据\n依据 [1] 和 [2].\n\n"
        "## 参考引用\n1. 来源一\n2. 来源二\n3. 来源三\n"
    )
    s = ev.parse_draft_structure(md)
    assert s.has_problem_section is True
    assert s.has_basis_section is True
    assert s.has_references_section is True
    assert s.missing_sections == []
    assert s.is_valid is True
    assert s.warn_lines() == []


def test_parse_draft_structure_missing_references() -> None:
    md = "## 问题摘要\nx\n## 政策依据\n依据 [1].\n"
    s = ev.parse_draft_structure(md)
    assert s.has_problem_section is True
    assert s.has_basis_section is True
    assert s.has_references_section is False
    assert s.missing_sections == ["参考引用"]
    assert s.is_valid is False
    warns = s.warn_lines()
    assert any("参考引用" in w for w in warns)


def test_parse_draft_structure_counts_citations() -> None:
    md = "## 问题背景\n引用 [1] [2] [3].\n## 政策依据\n[1] 与 [3].\n## 参考文献\n(略)\n"
    s = ev.parse_draft_structure(md)
    # [1][2][3] 出现, 3 个独立编号
    assert s.citation_count == 3


def test_parse_draft_structure_handles_chinese_brackets() -> None:
    md = "## 问题摘要\nx\n## 政策依据\n依据〔1〕与〔2〕.\n## 参考文献\n略\n"
    s = ev.parse_draft_structure(md)
    assert s.citation_count == 2


def test_parse_draft_structure_falls_back_to_source_line() -> None:
    """没有 [N] 编号时, 退回到 **来源**: a, b, c 计数."""
    md = (
        "## 问题摘要\nx\n"
        "**来源**: 国办发〔2019〕2 号, 国卫药政发〔2014〕51 号, 发改价格〔2011〕441 号\n"
        "## 政策依据\ny\n"
        "## 参考引用\nz\n"
    )
    s = ev.parse_draft_structure(md)
    assert s.citation_count == 3


def test_parse_draft_structure_handles_numbered_headings() -> None:
    """兼容 demo 报告的 '## 4. 可溯源引用清单' 这种带 N. 序号的标题."""
    md = (
        "## 1. 工作问题\n> 测试\n"
        "## 3. 问题摘要\n内容\n"
        "## 4. 政策依据\n内容\n"
        "## 5. 可溯源引用清单\n1. 来源一\n2. 来源二\n3. 来源三\n"
    )
    s = ev.parse_draft_structure(md)
    assert s.has_problem_section is True
    assert s.has_basis_section is True
    assert s.has_references_section is True
    assert s.missing_sections == []


# ── RecallMetrics ──────────────────────────────────────────


def test_compute_recall_full_hit() -> None:
    m = ev.compute_recall(
        searched_ids=["CON-health-policy-001", "CON-health-policy-002", "CON-other-999"],
        expected_ids=["CON-health-policy-001", "CON-health-policy-002"],
    )
    assert m.expected_count == 2
    assert m.hit_count == 2
    assert m.miss_count == 0
    assert m.recall == 1.0
    assert m.missing == []
    assert m.quality_grade() == "A"


def test_compute_recall_zero_hit() -> None:
    m = ev.compute_recall(
        searched_ids=["CON-other-999"],
        expected_ids=["CON-health-policy-001", "CON-health-policy-002"],
    )
    assert m.hit_count == 0
    assert m.miss_count == 2
    assert m.recall == 0.0
    assert m.missing == ["CON-health-policy-001", "CON-health-policy-002"]
    assert m.quality_grade() == "F"


def test_compute_recall_empty_expected() -> None:
    m = ev.compute_recall(searched_ids=["CON-x"], expected_ids=[])
    assert m.expected_count == 0
    assert m.recall == 0.0
    assert m.quality_grade() == "F"


@pytest.mark.parametrize(
    ("recall_value", "expected_grade"),
    [
        (0.95, "A"),
        (0.80, "A"),
        (0.79, "B"),
        (0.60, "B"),
        (0.59, "C"),
        (0.40, "C"),
        (0.39, "D"),
        (0.20, "D"),
        (0.19, "F"),
        (0.10, "F"),
        (0.0, "F"),
    ],
)
def test_recall_quality_grade_thresholds(recall_value: float, expected_grade: str) -> None:
    m = ev.RecallMetrics(
        expected_count=10,
        hit_count=int(round(recall_value * 10)),
        miss_count=10 - int(round(recall_value * 10)),
        recall=recall_value,
    )
    assert m.quality_grade() == expected_grade


# ── warn_lines ─────────────────────────────────────────────


def test_draft_structure_warn_lines() -> None:
    """验证 warn_lines 同时反映缺失节 + 引用数不足."""
    md = "## 问题摘要\nx\n## 政策依据\n[1] only\n"  # 缺参考引用 + 引用数 < 3
    s = ev.parse_draft_structure(md)
    warns = s.warn_lines()
    assert any("参考引用" in w for w in warns)
    assert any("引用数" in w and "< 3" in w for w in warns)


def test_draft_structure_warn_lines_all_ok() -> None:
    md = "## 问题摘要\n[1] 描述\n## 政策依据\n[1] [2] [3]\n## 参考引用\n略\n"
    s = ev.parse_draft_structure(md)
    assert s.warn_lines() == []


# ── 报告渲染 ──────────────────────────────────────────────


def test_render_eval_report_contains_grade() -> None:
    s = ev.DraftStructure(
        has_problem_section=True,
        has_basis_section=True,
        has_references_section=True,
        citation_count=5,
        missing_sections=[],
    )
    m = ev.RecallMetrics(expected_count=3, hit_count=3, miss_count=0, recall=1.0, missing=[])
    out = ev.render_eval_report(
        question="测试",
        expected_ids=["CON-a", "CON-b", "CON-c"],
        searched_ids=["CON-a", "CON-b", "CON-c"],
        structure=s,
        recall=m,
        elapsed_seconds=2.5,
    )
    assert "P29 E2E-DEMO 评估报告" in out
    assert "Recall" in out
    assert "A " in out or "| A" in out
    assert "结构校验" in out
    assert "改进建议" in out


# ── CLI 干跑 ───────────────────────────────────────────────


def test_eval_cli_with_dry_run(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """最小 demo 报告 + CLI 主流程跑通, 输出评估报告."""
    draft = tmp_path / "draft.md"
    draft.write_text(
        "# Phase 28 — E2E 卫健委工作场景演示证据\n"
        "> 生成时间: 2026-06-05T21:02:58 · 总耗时: 8.14s\n"
        "## 1. 工作问题\n"
        "> 测试问题\n"
        "## 3. 初稿正文\n"
        "### 问题背景\n引用 [1] [2] [3].\n"
        "### 政策依据\n依据 [1] [2].\n"
        "## 4. 可溯源引用清单\n"
        "1. 来源一\n2. 来源二\n3. 来源三\n"
        "## 5. gbrain / KOS 知识记录\n"
        "- 来源实体 IDs: `CON-health-policy-001`, `CON-health-policy-002`\n",
        encoding="utf-8",
    )
    output = tmp_path / "eval.md"
    rc = ev.main(
        [
            "--draft",
            str(draft),
            "--expected-policy-ids",
            "CON-health-policy-001,CON-health-policy-002,CON-health-policy-003",
            "--output",
            str(output),
        ]
    )
    assert rc == 0
    captured = capsys.readouterr()
    assert "评估完成" in captured.out
    assert output.exists()
    text = output.read_text(encoding="utf-8")
    assert "P29 E2E-DEMO 评估报告" in text
    # 2/3 命中 → 0.67 召回率 → B 等级
    assert "0.67" in text
    assert "B " in text or "| B" in text


def test_eval_cli_missing_draft(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    rc = ev.main(
        [
            "--draft",
            str(tmp_path / "nope.md"),
            "--expected-policy-ids",
            "CON-x",
        ]
    )
    assert rc == 1
