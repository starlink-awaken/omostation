#!/usr/bin/env python3
"""
BaseExtractor — 统一知识提取基类
消除两域提取器重复代码。
"""

from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
import re


class BaseExtractor:
    """统一知识提取基类"""

    # 通用实体提取模式
    PATTERNS = {
        "date": r'(\d{4}年?\d{1,2}月?\d{1,2}日?|\d{4}[-/]\d{1,2}[-/]\d{1,2})',
        "amount": r'(\d+[\.,，]*\d*\s*(万元|元|亿元|万|亿))',
        "org": r'([\u4e00-\u9fa5]{2,20}(委员会|局|中心|医院|公司|集团|学校|研究所))',
        "project": r'([\u4e00-\u9fa5]{2,30}项目)',
        "law_ref": r'(《[\u4e00-\u9fa5]+》)',
    }

    def __init__(self, domain_root: Path):
        self.domain_root = Path(domain_root)

    def extract_entities(self, text: str) -> Dict[str, List[str]]:
        """从文本中提取实体"""
        entities = {}
        for etype, pattern in self.PATTERNS.items():
            matches = re.findall(pattern, text)
            if matches:
                flat = [m[0] if isinstance(m, tuple) else m for m in matches]
                entities[etype] = list(set(flat))[:10]
        return entities

    def extract_from_file(self, file_path: Path) -> dict:
        """从单个文件提取知识"""
        text = file_path.read_text(encoding="utf-8")
        return {
            "file": str(file_path.relative_to(self.domain_root)),
            "char_count": len(text),
            "entities": self.extract_entities(text),
            "summary": self._make_summary(text),
            "extracted_at": datetime.now().isoformat(),
        }

    def extract_from_ocr(self, ocr_dir: Optional[Path] = None) -> List[dict]:
        """从 OCR 目录批量提取"""
        if ocr_dir is None:
            ocr_dir = self.domain_root / "_ocr_text"
        if not ocr_dir.exists():
            return []

        results = []
        for txt_file in sorted(ocr_dir.glob("*.txt")):
            if txt_file.name.startswith("_"):
                continue
            try:
                result = self.extract_from_file(txt_file)
                result["source"] = txt_file.stem
                results.append(result)
            except Exception as e:
                results.append({"source": txt_file.stem, "error": str(e)})
        return results

    def classify_domain(self, text: str, domain_keywords: Dict[str, List[str]]) -> List[str]:
        """根据关键词分类知识域"""
        scores = {}
        for domain, keywords in domain_keywords.items():
            score = sum(1 for kw in keywords if kw in text)
            if score > 0:
                scores[domain] = score
        if not scores:
            return ["综合"]
        return [d[0] for d in sorted(scores.items(), key=lambda x: -x[1])[:3]]

    def _make_summary(self, text: str, max_len: int = 200) -> str:
        """生成文本摘要"""
        lines = [l.strip() for l in text.split("\n") if l.strip() and not l.startswith("---")]
        summary = " ".join(lines[:5])
        if len(summary) > max_len:
            summary = summary[:max_len] + "..."
        return summary


if __name__ == "__main__":
    import json

    extractor = BaseExtractor(Path.cwd())
    results = extractor.extract_from_ocr()
    print(f"提取 {len(results)} 个文件")
    if results:
        print(json.dumps(results[0], ensure_ascii=False, indent=2))
