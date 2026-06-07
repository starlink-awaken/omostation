"""
ssot-kernel — extractor/ensemble.py
=====================================
集成提取器：模板高召回 + LLM 高精度合并。

流程：
1. 模板提取器快速提取全部候选（毫秒级）
2. LLM 批量验证候选（单次调用）
3. 合并结果：LLM 确认的保留，拒绝的丢弃，补充遗漏

目标 F1 > 0.8（模板 0.65 + LLM 0.5 → 合并后 > 0.8）
"""

from __future__ import annotations

import re
import sys

from .base import ExtractionCandidate, ExtractionResult, Extractor, TextSource
from .llm import LLMExtractor
from .template import TemplateExtractor

ENSEMBLE_PROMPT = """你是一个提取结果审核员。你的任务是基于原文验证一组提取候选。

## 原文（部分）

---原文开始---
{source_text}
---原文结束---

## 候选列表

以下是模板提取器从原文中提取的 {count} 个候选。请逐一判断：

{candidates_yaml}

## 输出格式

输出 YAML，包含 verified（确认存在的）和 rejected（不存在的）：

```yaml
verified:
  - id: person-yangbo
    reason: 出现在原文 "### person-yangbo" 段落
rejected:
  - id: person-liu-deputy
    reason: 原文中无对应条目

# 可选：原文中存在但候选列表遗漏的
missed:
  - id: person-liaison
    type: person
    reason: 原文有 ### person-liaison 条目但模板未提取
```

只输出 YAML，不要额外解释。"""


class EnsembleExtractor(Extractor):
    """集成提取器：模板 + LLM 验证"""

    def __init__(self, template: TemplateExtractor | None = None, llm: LLMExtractor | None = None):
        self.template = template or TemplateExtractor()
        self.llm = llm or LLMExtractor(auto_detect=True)

    @property
    def extractor_name(self) -> str:
        return f"ensemble(template+{self.llm.extractor_name})"

    def can_handle(self, source: TextSource) -> bool:
        return self.template.can_handle(source)

    def extract(self, source: TextSource) -> ExtractionResult:
        # 1. 模板先提取
        template_result = self.template.extract(source)
        if not template_result.candidates:
            # 模板无结果 → 回退到纯 LLM
            if self.llm.can_handle(source):
                return self.llm.extract(source)
            return template_result

        # 2. LLM 验证候选
        if not self.llm.can_handle(source):
            # LLM 不可用 → 直接返回模板结果
            return template_result

        verified = self._verify_candidates(source.raw_text, template_result.candidates)

        # 3. 合并结果
        all_candidates = []
        seen_ids = set()

        for c in verified.get("verified", []):
            eid = c.get("id", "")
            if eid and eid not in seen_ids:
                seen_ids.add(eid)
                all_candidates.append(
                    ExtractionCandidate(
                        category="entity",
                        id=eid,
                        content={"id": eid, "name": eid, "source": "ensemble/verified"},
                        confidence=0.85,
                    )
                )

        for c in verified.get("missed", []):
            eid = c.get("id", "")
            if eid and eid not in seen_ids:
                seen_ids.add(eid)
                all_candidates.append(
                    ExtractionCandidate(
                        category=c.get("type", "entity"),
                        id=eid,
                        content={"id": eid, "name": eid, "source": "ensemble/llm-gap"},
                        confidence=0.65,  # LLM 补充的置信度稍低
                    )
                )

        # 如果 LLM 没返回有效结果，回退到模板
        if not all_candidates:
            return template_result

        return ExtractionResult(
            candidates=all_candidates,
            summary=f"集成提取: {len(template_result.candidates)}候选 → LLM验证 → {len(all_candidates)}最终",
            confidence=0.85,
        )

    def _verify_candidates(self, source_text: str, candidates: list) -> dict:
        """调用 LLM 验证候选列表"""

        # 截断原文到 LLM 可处理范围
        text = source_text
        if len(text) > 12000:
            text = text[:12000] + f"\n...(截断，原文{len(source_text)}字)"

        # 构建候选 YAML 摘要
        candidate_lines = []
        for c in candidates[:60]:  # 最多 60 个
            cid = c.id or ""
            cat = c.category
            name = c.content.get("name", cid)[:40]
            candidate_lines.append(f'  - id: "{cid}"')
            candidate_lines.append(f"    type: {cat}")
            candidate_lines.append(f'    name: "{name}"')
        candidate_yaml = "\n".join(candidate_lines)

        prompt = ENSEMBLE_PROMPT.format(
            source_text=text,
            count=len(candidates),
            candidates_yaml=candidate_yaml,
        )

        try:
            response = self.llm.backend.complete(
                "你是一个严格的提取结果审核员。输出纯 YAML。",
                prompt,
                temperature=0.05,
            )
        except Exception as e:
            print(f"  ⚠️ LLM 验证失败: {e}（回退到纯模板结果）", file=sys.stderr)
            return {"verified": [], "rejected": [], "missed": []}

        # 解析 LLM 的 YAML 输出
        return self._parse_verification(response)

    def _parse_verification(self, response: str) -> dict:
        """解析 LLM 验证结果"""
        import yaml

        cleaned = response.strip()
        yaml_block = re.search(r"```(?:yaml)?\s*\n(.*?)\n\s*```", cleaned, re.DOTALL)
        if yaml_block:
            cleaned = yaml_block.group(1)

        try:
            data = yaml.safe_load(cleaned)
            if isinstance(data, dict):
                return {
                    "verified": data.get("verified", []),
                    "rejected": data.get("rejected", []),
                    "missed": data.get("missed", []),
                }
        except Exception:
            pass

        return {"verified": [], "rejected": [], "missed": []}
