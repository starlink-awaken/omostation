#!/usr/bin/env python3
"""
国转中心控制器 — 继承 BaseController
保留域特有逻辑（平台资料 + 影像处理）。
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "workspace-next-phase" / "projects" / "domain-kems" / "src"))

from domain_kems import BaseController


class TransformationCenterController(BaseController):
    """国转中心控制器"""

    ROOT = Path("/Users/xiamingxing/Documents/@工作文档/国转中心")

    def __init__(self):
        super().__init__(self.ROOT)

    def domain_specific_scan(self) -> dict:
        result = {}
        knowledge_dir = self.root / "_knowledge"
        if knowledge_dir.exists():
            domain_counts = {}
            for md_file in knowledge_dir.rglob("*.md"):
                if md_file.name == "INDEX.md":
                    continue
                parts = md_file.relative_to(knowledge_dir).parts
                if len(parts) > 1:
                    domain = parts[0]
                    domain_counts[domain] = domain_counts.get(domain, 0) + 1
            result["knowledge_domains"] = domain_counts
            result["total_knowledge_files"] = sum(domain_counts.values())
        return result


if __name__ == "__main__":
    controller = TransformationCenterController()
    report = controller.run()
    print(json.dumps(report, ensure_ascii=False, indent=2))
