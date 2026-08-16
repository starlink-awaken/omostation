"""P29-W0-E2E-EVAL — 卫健委 E2E-DEMO 质量评估脚本.

在 e2e_health_demo.py 跑完初稿/报告后, 对结果做三件事:
  1. 解析初稿 Markdown 结构, 校验固定节(问题摘要/政策依据/参考引用)是否齐全
  2. 用 recall = hit / expected 评估 KOS 检索召回率
  3. 把以上两点 + 改进建议渲染成一份评估报告, 供下次真用时自检

设计目标:
  - 不修改 e2e_health_demo.py 业务逻辑
  - CLI 可独立运行(可与 demo 串联)
  - 召回率量化分级(A/B/C/D/F), 结构缺失直接 warn
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal

# ── 数据结构 ────────────────────────────────────────────────


@dataclass
class DraftStructure:
    """解析后的初稿结构, 反映是否符合固定模板."""

    has_problem_section: bool  ## 问题摘要 / ## 问题 / ## 问题背景
    has_basis_section: bool  ## 政策依据 / ## 主要内容
    has_references_section: bool  ## 参考引用 / ## 参考文献 / ## 4. 可溯源引用清单
    citation_count: int  # 文中 [1]/[2] 编号引用数
    missing_sections: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return (
            self.has_problem_section
            and self.has_basis_section
            and self.has_references_section
            and not self.missing_sections
        )

    def warn_lines(self) -> list[str]:
        """返回需要警告的行(缺失节 + 引用数)."""
        warnings: list[str] = []
        if not self.has_problem_section:
            warnings.append("缺失「问题摘要」节(期望 ## 问题摘要 / ## 问题 / ## 问题背景)")
        if not self.has_basis_section:
            warnings.append("缺失「政策依据」节(期望 ## 政策依据 / ## 主要内容)")
        if not self.has_references_section:
            warnings.append("缺失「参考引用」节(期望 ## 参考引用 / ## 参考文献 / 引用清单节)")
        if self.citation_count < 3:
            warnings.append(f"引用数 {self.citation_count} < 3 阈值(任务验收要求 ≥ 3 个可溯源引用)")
        return warnings


@dataclass
class RecallMetrics:
    """召回率指标."""

    expected_count: int
    hit_count: int
    miss_count: int
    recall: float  # hit / expected (0.0 if expected == 0)
    missing: list[str] = field(default_factory=list)

    def quality_grade(self) -> Literal["A", "B", "C", "D", "F"]:
        """recall >= 0.8 → A, >= 0.6 → B, >= 0.4 → C, >= 0.2 → D, else F."""
        if self.recall >= 0.8:
            return "A"
        if self.recall >= 0.6:
            return "B"
        if self.recall >= 0.4:
            return "C"
        if self.recall >= 0.2:
            return "D"
        return "F"


# ── 解析器 ──────────────────────────────────────────────────


# 节标题识别(包含 demo 报告里的实际写法, 支持 `## 4. xxx` 这种带序号的标题)
_PROBLEM_PATTERNS = (r"^#{1,3}\s*(?:\d+\.\s*)?(?:问题摘要|问题背景|问题)\s*$",)
_BASIS_PATTERNS = (r"^#{1,3}\s*(?:\d+\.\s*)?(?:政策依据|主要内容|政策内容)\s*$",)
_REFERENCES_PATTERNS = (r"^#{1,3}\s*(?:\d+\.\s*)?(?:参考引用|参考文献|引用清单|可溯源引用清单)\s*$",)

# 引用编号正则(支持中英文方括号)
_CITATION_RE = re.compile(r"[\[〔]\s*(\d+)\s*[\]〕]")
# 引用号 + 来源映射(如 "**来源**: xxx, yyy" 一行内的多个来源)
_SOURCE_LINE_RE = re.compile(r"\*\*来源\*\*\s*[:：]\s*(.+?)$")


def parse_draft_structure(markdown: str) -> DraftStructure:
    """解析 Markdown 初稿, 校验固定节与引用数.

    既可解析 demo 脚本生成的初稿正文, 也可解析包含 demo 报告头部的完整报告
    (节标题识别兼容 demo 报告里的 `### 摘要` / `## 4. 可溯源引用清单` 等).
    """
    has_problem = False
    has_basis = False
    has_references = False

    for raw in markdown.splitlines():
        line = raw.strip()
        if not line:
            continue
        if any(re.match(p, line) for p in _PROBLEM_PATTERNS):
            has_problem = True
        elif any(re.match(p, line) for p in _BASIS_PATTERNS):
            has_basis = True
        elif any(re.match(p, line) for p in _REFERENCES_PATTERNS):
            has_references = True

    # 引用计数: 优先数 [N] 编号, 若完全没有再退回到数"来源:"行里的来源数
    citation_count = len(set(int(m) for m in _CITATION_RE.findall(markdown)))

    if citation_count == 0:
        for line in markdown.splitlines():
            m = _SOURCE_LINE_RE.search(line.strip())
            if m:
                items = [x.strip() for x in re.split(r"[,，、;；]", m.group(1)) if x.strip()]
                citation_count = max(citation_count, len(items))
        # 兜底: 报告"## 4. 可溯源引用清单"下的有序列表项
        if citation_count == 0 and "可溯源引用清单" in markdown:
            ref_section = markdown.split("可溯源引用清单", 1)[1]
            numbered = re.findall(r"^\s*\d+\.\s+\S+", ref_section, flags=re.MULTILINE)
            citation_count = max(citation_count, len(numbered))

    missing: list[str] = []
    if not has_problem:
        missing.append("问题摘要")
    if not has_basis:
        missing.append("政策依据")
    if not has_references:
        missing.append("参考引用")

    return DraftStructure(
        has_problem_section=has_problem,
        has_basis_section=has_basis,
        has_references_section=has_references,
        citation_count=citation_count,
        missing_sections=missing,
    )


def compute_recall(searched_ids: list[str], expected_ids: list[str]) -> RecallMetrics:
    """计算召回率指标.

    searched:  KOS 实际命中的政策 ID 列表
    expected:  期望命中的种子政策 ID 列表(如 SEED_POLICIES 里的 entity_id)
    """
    if not expected_ids:
        return RecallMetrics(expected_count=0, hit_count=0, miss_count=0, recall=0.0, missing=[])

    searched_set = set(searched_ids)
    expected_set = set(expected_ids)
    hit = sorted(searched_set & expected_set)
    miss = sorted(expected_set - searched_set)
    hit_count = len(hit)
    recall = hit_count / len(expected_set)
    return RecallMetrics(
        expected_count=len(expected_set),
        hit_count=hit_count,
        miss_count=len(miss),
        recall=recall,
        missing=miss,
    )


# ── 报告渲染 ────────────────────────────────────────────────


def _grade_emoji(grade: str) -> str:
    return {"A": "优秀", "B": "良好", "C": "合格", "D": "待改进", "F": "不合格"}.get(grade, grade)


def _improvement_rows(recall: RecallMetrics, structure: DraftStructure) -> list[tuple[str, str, str]]:
    """生成"当前 → 建议"改进表格行."""
    rows: list[tuple[str, str, str]] = []

    grade = recall.quality_grade()
    if recall.expected_count == 0:
        current = "N/A (无期望种子)"
        suggestion = "提供 --expected-policy-ids 才能评估召回率"
    else:
        current = f"{recall.recall:.2f} ({grade})"
        if grade in ("A", "B"):
            suggestion = "维持当前关键词策略, 可考虑扩大种子政策覆盖"
        elif grade in ("C", "D"):
            suggestion = "增加种子政策数 / 在问题中显式补充核心关键词(政策名/年份/发文字号)"
        else:
            suggestion = "重写 _extract_keywords 加入政策同义词扩展, 或预建更全的政策种子库"
    rows.append(("召回率", current, suggestion))

    if structure.citation_count >= 3:
        rows.append(
            (
                "引用数",
                f"{structure.citation_count}",
                f"已经达到 ≥ 3 阈值, 当前 {structure.citation_count} 条",
            )
        )
    else:
        rows.append(
            (
                "引用数",
                f"{structure.citation_count}",
                "引用不足 3 阈值, 建议让 LLM 在每节末尾显式插入 [1][2][3] 编号引用",
            )
        )

    present = sum([structure.has_problem_section, structure.has_basis_section, structure.has_references_section])
    rows.append(
        (
            "结构完整性",
            f"{present}/3",
            "在 system prompt 中强制要求 '## 政策依据' 与 '## 参考引用' 节, 否则 warn 提醒起草人补节"
            if present < 3
            else "3/3 全部命中, 维持模板",
        )
    )
    return rows


def render_eval_report(
    question: str,
    expected_ids: list[str],
    searched_ids: list[str],
    structure: DraftStructure,
    recall: RecallMetrics,
    elapsed_seconds: float,
    draft_path: Path | None = None,
) -> str:
    """渲染评估报告 Markdown."""
    grade = recall.quality_grade()
    today = datetime.now().strftime("%Y-%m-%d")
    hits = sorted(set(searched_ids) & set(expected_ids))
    rows = _improvement_rows(recall, structure)
    warns = structure.warn_lines()

    lines: list[str] = [
        f"# P29 E2E-DEMO 评估报告 — {today}",
        "",
        f"> 工作问题: {question}",
        f"> 实际运行: {elapsed_seconds:.2f}s · KOS 命中 {len(searched_ids)} 条 · 引用 {structure.citation_count} 条",
        (f"> 初稿文件: `{draft_path}`" if draft_path else ""),
        "",
        "## 召回率评估",
        "",
        "| 指标 | 值 |",
        "|---|---|",
        f"| 期望种子数 | {recall.expected_count} |",
        f"| 命中数 | {recall.hit_count} |",
        f"| 缺失 | {', '.join(recall.missing) if recall.missing else '(无)'} |",
        f"| 命中明细 | {', '.join(hits) if hits else '(无)'} |",
        f"| **Recall** | **{recall.recall:.2f}** |",
        f"| 等级 | {grade} ({_grade_emoji(grade)}) |",
        "",
        "## 结构校验",
        "",
        f"- {'✅' if structure.has_problem_section else '❌'} 问题摘要节",
        f"- {'✅' if structure.has_basis_section else '❌'} 政策依据节",
        f"- {'✅' if structure.has_references_section else '❌'} 参考引用节",
        f"- 引用数: {structure.citation_count}",
    ]

    if warns:
        lines.extend(["", "### 警告", ""])
        for w in warns:
            lines.append(f"- ⚠️ {w}")
    else:
        lines.extend(["", "> 全部校验通过, 无警告.", ""])

    lines.extend(
        [
            "",
            "## 改进建议",
            "",
            "| 维度 | 当前 | 建议 |",
            "|---|---|---|",
        ]
    )
    for dim, cur, sug in rows:
        lines.append(f"| {dim} | {cur} | {sug} |")

    lines.extend(
        [
            "",
            "## 调用方法",
            "",
            "```bash",
            "# 1. 跑 demo 生成初稿",
            "uv run python scripts/e2e_health_demo.py \\",
            '    --question "<工作问题>" \\',
            "    --output /tmp/draft.md",
            "",
            "# 2. 跑 eval 评估初稿",
            "uv run python scripts/e2e_health_eval.py \\",
            "    --draft /tmp/draft.md \\",
            "    --expected-policy-ids CON-health-policy-001,CON-health-policy-002,CON-health-policy-003 \\",
            "    --output .omo/_delivery/phase28-e2e-eval-report.md",
            "```",
            "",
            "## 关联文件",
            "",
            "- 评估脚本: `projects/kairon/scripts/e2e_health_eval.py`",
            "- 测试: `projects/kairon/tests/scripts/test_e2e_health_eval.py`",
            "- 评估对象: `projects/kairon/scripts/e2e_health_demo.py`",
            "- 任务 YAML: `.omo/tasks/planned/P29-W0-E2E-EVAL.yaml`",
            "",
        ]
    )
    return "\n".join(line for line in lines if line is not None)


# ── CLI ─────────────────────────────────────────────────────


def _read_draft_ids(draft_path: Path) -> list[str]:
    """从 demo 报告里抓取 '来源实体 IDs:' 后面列出的命中 ID.

    兼容 demo 报告里的两种写法:
      - 反引号包裹: `CON-xxx`
      - 逗号分隔
    """
    text = draft_path.read_text(encoding="utf-8")
    marker = "来源实体 IDs:"
    if marker not in text:
        return []
    tail = text.split(marker, 1)[1]
    # 截到下一个 markdown 段标题或空行+换行
    tail = tail.split("\n\n", 1)[0]
    return [m.group(1) for m in re.finditer(r"`(CON-[A-Za-z0-9_-]+)`", tail)]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="P29-W0-E2E-EVAL: 卫健委 E2E-DEMO 初稿质量评估(结构 + 召回率)",
    )
    parser.add_argument("--draft", required=True, help="e2e_health_demo.py 生成的报告/Markdown 路径")
    parser.add_argument(
        "--expected-policy-ids",
        required=True,
        help="逗号分隔的期望命中政策 IDs(如 CON-health-policy-001,CON-health-policy-002)",
    )
    parser.add_argument(
        "--searched-ids",
        default=None,
        help="KOS 实际命中 IDs(逗号分隔); 不传则尝试从 --draft 报告里解析",
    )
    parser.add_argument(
        "--elapsed-seconds",
        type=float,
        default=0.0,
        help="demo 链路耗时(秒), 不传则从报告里解析或记 0",
    )
    parser.add_argument("--output", default=None, help="评估报告输出路径(可选)")
    parser.add_argument(
        "--question",
        default=None,
        help="工作问题(用于报告头); 不传则从 draft 里找 '## 1. 工作问题' 段落",
    )
    args = parser.parse_args(argv)

    draft_path = Path(args.draft).expanduser()
    if not draft_path.exists():
        print(f"[E2E-EVAL] ❌ 找不到 draft 文件: {draft_path}", file=sys.stderr)
        return 1

    markdown = draft_path.read_text(encoding="utf-8")
    structure = parse_draft_structure(markdown)

    expected_ids = [s.strip() for s in args.expected_policy_ids.split(",") if s.strip()]

    if args.searched_ids:
        searched_ids = [s.strip() for s in args.searched_ids.split(",") if s.strip()]
    else:
        searched_ids = _read_draft_ids(draft_path)

    recall = compute_recall(searched_ids=searched_ids, expected_ids=expected_ids)

    # 解析问题(从报告头)
    question = args.question
    if not question:
        m = re.search(r"##\s*1\.\s*工作问题\s*\n+>\s*(.+?)\s*$", markdown, flags=re.MULTILINE)
        if m:
            question = m.group(1).strip()
        else:
            question = "(未提供)"

    # 解析耗时(从报告头)
    elapsed = args.elapsed_seconds
    if elapsed == 0.0:
        m = re.search(r"总耗时[:：]\s*([\d.]+)\s*s", markdown)
        if m:
            try:
                elapsed = float(m.group(1))
            except ValueError:
                elapsed = 0.0

    report_md = render_eval_report(
        question=question,
        expected_ids=expected_ids,
        searched_ids=searched_ids,
        structure=structure,
        recall=recall,
        elapsed_seconds=elapsed,
        draft_path=draft_path,
    )

    print("[E2E-EVAL] 评估完成")
    print(
        f"  结构: problem={structure.has_problem_section} "
        f"basis={structure.has_basis_section} "
        f"refs={structure.has_references_section} "
        f"citations={structure.citation_count}"
    )
    print(f"  召回率: {recall.recall:.2f} ({recall.quality_grade()}) hit={recall.hit_count}/{recall.expected_count}")
    if structure.warn_lines():
        print("  警告:")
        for w in structure.warn_lines():
            print(f"    - {w}")

    if args.output:
        out = Path(args.output).expanduser()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(report_md, encoding="utf-8")
        print(f"  报告已写入: {out}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
