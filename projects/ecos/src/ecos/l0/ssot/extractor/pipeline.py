"""
ssot-kernel — extractor/pipeline.py
=====================================
提取流水线：统一入口，串联多路提取器 → 校验 → 写入。

工作流：
1. 接收原始文本（TextSource）
2. 依次尝试已注册的提取器（template → interactive → ...）
3. 合并提取结果
4. 校验 -> 用户确认 -> 写入领域 YAML
"""

from __future__ import annotations

from .base import (
    CandidateValidator,
    ExtractionResult,
    Extractor,
    TextSource,
    ValidationResult,
    YamlWriter,
)
from .template import TemplateExtractor


class ExtractionPipeline:
    """提取流水线——从原始文本到领域 YAML 的一站式入口"""

    def __init__(self, domain_dir: str = ""):
        self.domain_dir = domain_dir
        self.extractors: list[Extractor] = []
        self._llm_extractor = None  # 懒加载 + 缓存
        self._llm_checked = False  # 只检测一次
        self._llm_failed = False  # 标记检测失败，跳过后续重试
        self.extractors.append(TemplateExtractor())

    def _get_llm(self):
        """懒加载 LLM 提取器——只在模板无候选时才检测（结果缓存，只检测一次）"""
        if self._llm_checked:
            return self._llm_extractor
        self._llm_checked = True
        if self._llm_failed:
            return None
        try:
            from .llm import LLMExtractor

            llm = LLMExtractor(auto_detect=True)
            if llm.available:
                self._llm_extractor = llm
                import sys

                print("  🔄 LLM 兜底已就绪", file=sys.stderr)
            else:
                self._llm_failed = True
        except Exception:
            self._llm_failed = True
        return self._llm_extractor

    def register_extractor(self, extractor: Extractor):
        """注册自定义提取器"""
        self.extractors.append(extractor)

    def run(self, source: TextSource, auto_write: bool = False, auto_confirm: bool = False) -> dict:
        """执行完整提取流水线。

        Args:
            source: 原始文本输入
            auto_write: 提取后自动写入 YAML
            auto_confirm: 自动确认（跳过确认步骤）

        Returns:
            {
                "result": ExtractionResult,
                "validation": ValidationResult,
                "applied_files": [str],  # 如果 auto_write=True
                "errors": [str],
            }
        """
        errors = []
        all_candidates = []

        # 1. 模板提取器先跑（毫秒级、无 Ollama 检测）
        for extractor in self.extractors:
            if not extractor.can_handle(source):
                continue
            try:
                result = extractor.extract(source)
                all_candidates.extend(result.candidates)
                for err in result.errors:
                    errors.append(f"[{extractor.extractor_name}] {err}")
            except Exception as e:
                errors.append(f"[{extractor.extractor_name}] 执行异常: {e}")

        if not all_candidates:
            # 2. 模板无候选 → 尝试 LLM 兜底
            llm = self._get_llm()
            if llm:
                import sys

                print("  🔄 模板无候选，尝试 LLM 提取...", file=sys.stderr)
                try:
                    llm_result = llm.extract(source)
                    all_candidates.extend(llm_result.candidates)
                    for err in llm_result.errors:
                        errors.append(f"[llm] {err}")
                except Exception as e:
                    errors.append(f"[llm] {e}")

        if not all_candidates:
            # 无候选 -> 生成错误提示
            return {
                "result": ExtractionResult(
                    summary="未能从输入中提取任何结构化信息。",
                    errors=errors
                    + [
                        "可能原因: 输入格式不被当前模板支持",
                        "解决: a) 使用交互式提取逐步引导",
                        "      b) 注册自定义模板模式",
                        "      c) 先用 LLM 将文本结构化后再传入",
                    ],
                ),
                "validation": ValidationResult(passed=False),
                "errors": errors,
            }

        # 2. 合并候选
        merged = ExtractionResult(candidates=all_candidates)

        # 3. 校验
        validator = CandidateValidator(existing_domain_dir=self.domain_dir)
        validation = validator.validate(merged)

        # 4. 写入
        applied_files = []
        if auto_write and validation.passed:
            try:
                writer = YamlWriter(self.domain_dir)
                applied_files = writer.apply(merged, auto_confirm=auto_confirm)
            except Exception as e:
                errors.append(f"写入失败: {e}")

        return {
            "result": merged,
            "validation": validation,
            "applied_files": applied_files,
            "errors": errors,
        }

    def suggest_manual(self, source: TextSource) -> str:
        """当自动提取失败时，生成人工干预建议"""
        lines = [
            "## 自动提取未产出有效结果",
            "",
            f"来源: {source.source_name or source.source_type}",
            f"长度: {len(source.raw_text)} 字",
            "",
            "### 建议行动",
            "",
            "**方案一：使用交互式提取（推荐）**",
            "",
            "可以按类别逐步提取：",
            "  1. 先提取实体（组织/角色/项目）",
            "  2. 再提取事实（政策/数据）",
            "  3. 再提取推论和规则",
            "",
            "每步我都会引导你填写必要字段。",
            "",
            "**方案二：注册自定义模板**",
            "",
            "如果输入有固定格式，可以在 extractor/template.py 中",
            "添加一个 TemplatePattern，然后用模板提取器自动处理。",
            "",
            "  示例：",
            "  TemplatePattern(",
            '      name="my_template",',
            '      category="fact",',
            '      title_pattern=r"^(##\\s+.*$)",',
            '      field_patterns={"id": r"\\\\b(DAT-[\\\\w-]+)"},',
            "  )",
            "",
            "**方案三：先用 LLM 预处理**",
            "",
            "将原始文本先发给 Claude，让其结构化后再输入提取层：",
            '  "请从以下内容中提取实体和事实，输出 YAML 格式："',
            "",
        ]
        return "\n".join(lines)
