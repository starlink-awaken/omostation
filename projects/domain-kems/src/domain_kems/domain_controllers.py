#!/usr/bin/env python3
"""
域控制器 — 继承 BaseController，ROOT 路径配置化
从 ~/.config/domain/config.yaml 加载域配置
"""

from pathlib import Path
from domain_kems import BaseController, DomainConfig


class HealthCommissionController(BaseController):
    def __init__(self):
        config = DomainConfig()
        root = config.get_path("卫健委")
        super().__init__(root)

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


class LandPlanningController(BaseController):
    def __init__(self):
        config = DomainConfig()
        root = config.get_path("规自委")
        super().__init__(root)

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
        return result


class TransformationCenterController(BaseController):
    def __init__(self):
        config = DomainConfig()
        root = config.get_path("国转中心")
        super().__init__(root)

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
        return result


class ContractLawController(BaseController):
    def __init__(self):
        config = DomainConfig()
        root = config.get_path("合同法规")
        super().__init__(root)

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
        return result
