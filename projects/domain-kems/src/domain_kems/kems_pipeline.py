#!/usr/bin/env python3
"""
KEMS Pipeline — 统一知识工程流水线
从各域 _control/tools/ 下沉，复用 BaseExtractor + BaseController。
提供 extract → fuse → index 三阶段能力。
"""

from pathlib import Path
from datetime import datetime
from typing import Dict, List
import json


class KEMPipeline:
    """知识工程流水线：提取 → 融合 → 索引"""

    def __init__(self, domain_root: Path):
        self.domain_root = Path(domain_root)
        self.knowledge_dir = self.domain_root / "_knowledge"
        self.ocr_dir = self.domain_root / "_ocr_text"

    def extract(self) -> dict:
        """Stage 1: 知识提取（从 OCR 文本）"""
        from domain_kems import BaseExtractor

        extractor = BaseExtractor(self.domain_root)
        keywords = self._get_domain_keywords()
        entries = extractor.extract_from_ocr(self.ocr_dir)

        # Classify domains
        for entry in entries:
            text = entry.get("summary", "")
            entry["domains"] = extractor.classify_domain(text, keywords)

        report = {
            "domain": self.domain_root.name,
            "extracted_at": datetime.now().isoformat(),
            "total_files": len(entries),
            "entries": entries,
        }

        # Save report
        report_path = self.knowledge_dir / "_kems_extraction_report.json"
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        return report

    def fuse(self) -> dict:
        """Stage 2: 知识融合（构建图谱）"""
        from domain_kems import BasePredictor

        predictor = BasePredictor(self.domain_root)
        stale_docs = predictor.detect_stale_docs()

        # Build simple graph from extraction report
        extraction_path = self.knowledge_dir / "_kems_extraction_report.json"
        graph = {"documents": {}, "relationships": [], "domain_index": {}}

        if extraction_path.exists():
            extraction = json.loads(extraction_path.read_text(encoding="utf-8"))
            for entry in extraction.get("entries", []):
                source = entry.get("source", "")
                graph["documents"][source] = entry
                for domain in entry.get("domains", []):
                    graph["domain_index"].setdefault(domain, []).append(source)

        stale_count = len(stale_docs)

        # Save graph
        graph_path = self.knowledge_dir / "_kems_graph.json"
        graph_path.write_text(json.dumps(graph, ensure_ascii=False, indent=2), encoding="utf-8")

        fusion_report = {
            "domain": self.domain_root.name,
            "fused_at": datetime.now().isoformat(),
            "documents": len(graph["documents"]),
            "relationships": len(graph["relationships"]),
            "domains": list(graph["domain_index"].keys()),
        }

        fusion_path = self.knowledge_dir / "_kems_fusion_report.json"
        fusion_path.write_text(json.dumps(fusion_report, ensure_ascii=False, indent=2), encoding="utf-8")

        # Save markdown summary
        md_lines = [
            f"# {self.domain_root.name} — KEMS 融合报告",
            "",
            f"> **融合时间**: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            f"> **文档数**: {fusion_report['documents']}",
            f"> **知识域**: {len(fusion_report['domains'])} 个",
            "",
            "## 知识域分布",
            "",
        ]
        for domain, sources in sorted(graph["domain_index"].items()):
            md_lines.append(f"### {domain} ({len(sources)})")
            for s in sources[:10]:
                md_lines.append(f"- {s}")
            if len(sources) > 10:
                md_lines.append(f"- ... +{len(sources)-10}")
            md_lines.append("")

        md_path = self.knowledge_dir / "_kems_fusion_report.md"
        md_path.write_text("\n".join(md_lines), encoding="utf-8")

        return fusion_report

    def _get_domain_keywords(self) -> Dict[str, List[str]]:
        """获取域关键词（可扩展）"""
        return {
            "信息化建设": ["机房", "网络", "服务器", "数据库", "系统平台"],
            "政策法规": ["规定", "办法", "细则", "通知", "条例"],
            "项目管理": ["招标", "投标", "监理", "验收", "变更"],
            "网络安全": ["等保", "安全", "测评", "防火墙"],
            "服务运维": ["运维", "维护", "保修", "服务", "外包"],
            "资金管理": ["预算", "决算", "资金", "付款", "发票"],
            "数据管理": ["数据", "共享", "交换", "接口", "采集"],
        }


if __name__ == "__main__":
    import sys

    domain = sys.argv[1] if len(sys.argv) > 1 else "卫健委"
    root = Path("/Users/xiamingxing/Documents/@工作文档") / domain
    pipeline = KEMPipeline(root)

    print(f"KEMS Pipeline: {domain}")
    print("\n[Stage 1] 提取...")
    r1 = pipeline.extract()
    print(f"  提取完成: {r1['total_files']} 文件")

    print("\n[Stage 2] 融合...")
    r2 = pipeline.fuse()
    print(f"  融合完成: {r2['documents']} 文档, {len(r2['domains'])} 知识域")
