#!/usr/bin/env python3
"""
卫健委控制器 — 继承 BaseController
消除 80% 重复代码，保留域特有逻辑（jingbao 传感器 + CR 规则）。
"""

import sys
import json
from pathlib import Path

# 添加 domain-kems 到路径
sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "workspace-next-phase" / "projects" / "domain-kems" / "src"))

from domain_kems import BaseController


class HealthCommissionController(BaseController):
    """卫健委控制器 — 继承基类，保留域特有传感器"""

    ROOT = Path("/Users/xiamingxing/Documents/@工作文档/卫健委")

    def __init__(self):
        super().__init__(self.ROOT)
        self.jingbao_dir = self.root / "_control" / "_jingbao"
        self.cr_rules_file = self.root / "_control" / "cr-rules.json"

    def domain_specific_scan(self) -> dict:
        """域特有扫描：jingbao 状态 + CR 规则"""
        result = {}

        # 1. jingbao 传感器
        if self.jingbao_dir.exists():
            jingbao_files = list(self.jingbao_dir.glob("*.md"))
            result["jingbao_count"] = len(jingbao_files)
            result["jingbao_latest"] = (
                max(f.stat().st_mtime for f in jingbao_files)
                if jingbao_files
                else None
            )

        # 2. CR 规则加载
        if self.cr_rules_file.exists():
            try:
                rules = json.loads(self.cr_rules_file.read_text(encoding="utf-8"))
                result["cr_rules_count"] = len(rules.get("rules", []))
            except Exception:
                result["cr_rules_count"] = 0

        # 3. 项目统计
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
    controller = HealthCommissionController()
    report = controller.run()
    print(json.dumps(report, ensure_ascii=False, indent=2))
