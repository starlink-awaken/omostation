"""
FormalPipeline v4 — 四阶段形式化知识推理管线
===============================================
Phase 1: LLM提取(降级规则引擎) → 结构化知识
Phase 2: 本体对齐 + 符号化 → ABox/TBox
Phase 3: 形式推理(零LLM) → 确定/推测/不确定结论
Phase 4: LLM解读 → 自然语言报告
"""

from pathlib import Path
from typing import Any


class FormalPipeline:
    """四阶段形式化推理管线"""

    def __init__(self, enhancer: Any = None) -> None:
        self.enhancer = enhancer
        self.results: dict[Any, Any] = {}

    def run(self, text: str) -> dict:
        """执行完整四阶段管线"""
        # Phase 1+2: 提取 + 符号化
        try:
            from ontoderive.reasoners.formalize import Formalizer
        except ImportError:
            from ontoderive.reasoners.formalize import Formalizer
        fz = Formalizer(enhancer=self.enhancer)
        knowledge = fz.extract_from_text(text)
        self.results["phase1"] = {
            "facts": len(knowledge.facts),
            "entities": len(knowledge.entities),
            "inferences": len(knowledge.inferences),
        }

        from ontoderive.reasoners.reasoner_formal import FormalReasoner

        fr = FormalReasoner()
        conclusions = fr.reason(knowledge)
        self.results["phase3"] = fr.summary()

        # Phase 4: LLM解读
        report = self._interpret(conclusions, knowledge)

        return {
            "knowledge": knowledge,
            "conclusions": conclusions,
            "report": report,
            "summary": {
                "facts": len(knowledge.facts),
                "entities": len(knowledge.entities),
                "conclusions_total": len(conclusions),
                "certain": fr.summary()["certain"],
                "probable": fr.summary()["probable"],
                "uncertain": fr.summary()["uncertain"],
            },
        }

    def _interpret(self, conclusions: Any, knowledge: Any) -> str:
        """Phase 4: 将形式结论解读为自然语言报告"""
        lines = ["# 形式化知识推理报告\n"]
        lines.append("## 知识规模\n")
        lines.append(f"- 事实: {len(knowledge.facts)}条")
        lines.append(f"- 实体: {len(knowledge.entities)}个")
        lines.append(f"- 推论: {len(knowledge.inferences)}条\n")

        certain = [c for c in conclusions if c.certainty == "certain"]
        probable = [c for c in conclusions if c.certainty == "probable"]
        uncertain = [c for c in conclusions if c.certainty == "uncertain"]

        if certain:
            lines.append("## 确定结论 (逻辑必然)\n")
            for c in certain:
                lines.append(f"- **[{c.method}]** {c.conclusion} (置信度:{c.confidence:.0%})")

        if probable:
            lines.append("\n## 推测建议 (基于规则)\n")
            for c in probable:
                lines.append(f"- **[{c.method}]** {c.conclusion} (置信度:{c.confidence:.0%})")

        if uncertain:
            lines.append("\n## 不确定性标注\n")
            for c in uncertain:
                lines.append(f"- **[{c.method}]** {c.conclusion}")

        # LLM增强解读
        if self.enhancer and self.enhancer.available:
            try:
                summary_text = "\n".join(c.conclusion for c in conclusions[:10])
                llm_interpret = self.enhancer._call(
                    f"将以下推理结论解读为用户友好的建议。每条建议一行。\n{summary_text}", "你是知识工程分析专家。", 0.3
                )
                if llm_interpret:
                    lines.append("\n## LLM深度解读\n")
                    for line in llm_interpret.split("\n"):
                        if line.strip() and len(line.strip()) > 10:
                            lines.append(f"- {line.strip()}")
            except Exception:
                lines.append("\n## LLM解读\n(LLM不可用, 以上为规则引擎结论)")

        return "\n".join(lines)

    def save_report(self, output_dir: Any, report_text: Any = "") -> None:
        """保存报告到文件"""
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        (out / "formal-report.md").write_text(report_text)
        print(f"[pipeline_v4] ✅ 报告: {out}/formal-report.md")
