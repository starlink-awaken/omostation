#!/usr/bin/env python3
"""
Generate INDEX-KNOWLEDGE.md from .omo/_knowledge/ scan.

Owner: governance-team
Trigger: 新增 ADR / 新增审计 / 新增模式
"""

import os
from pathlib import Path
import datetime
from datetime import UTC
import re

SCRIPT_DIR = Path(__file__).parent
WORKSPACE_ROOT = SCRIPT_DIR.parent.parent
KNOWLEDGE_DIR = WORKSPACE_ROOT / ".omo" / "_knowledge"
INDEX_FILE = WORKSPACE_ROOT / "docs" / "INDEX-KNOWLEDGE.md"

TEMPLATE_HEADER = """# INDEX-KNOWLEDGE.md — 知识资产统一索引

> **维护规则**
> - owner: governance-team
> - trigger: 新增 ADR / 新增审计 / 新增模式
> - method: 脚本生成 (bin/ssot/gen-knowledge-index.py)
> - validation: ADR 数与实际目录一致
> - status: active
> - created_at: 2026-07-14
> - generated_at: {generated_at}

---

"""

def scan_knowledge_dir():
    categories = {}
    
    # Scan decisions (ADRs)
    decisions_dir = KNOWLEDGE_DIR / "decisions"
    if decisions_dir.exists():
        categories["adrs"] = []
        for f in sorted(decisions_dir.glob("*.md")):
            if f.is_file():
                categories["adrs"].append(f.name)
    
    # Scan audits
    audits_dir = KNOWLEDGE_DIR / "audits"
    if audits_dir.exists():
        categories["audits"] = []
        for f in sorted(audits_dir.glob("*.md")):
            if f.is_file():
                categories["audits"].append(f.name)
    
    # Scan patterns
    patterns_dir = KNOWLEDGE_DIR / "patterns"
    if patterns_dir.exists():
        categories["patterns"] = []
        for f in sorted(patterns_dir.glob("*.md")):
            if f.is_file():
                categories["patterns"].append(f.name)
    
    # Scan other dirs
    other_dirs = ["design", "management", "process", "reference", "summaries"]
    for dir_name in other_dirs:
        dir_path = KNOWLEDGE_DIR / dir_name
        if dir_path.exists():
            categories[dir_name] = []
            for f in sorted(dir_path.glob("*.md")):
                if f.is_file():
                    categories[dir_name].append(f.name)
    
    return categories

def generate_overview(categories):
    overview = """## 知识资产概览

| 类型 | 位置 | 说明 |
|------|------|------|
| ADR 决策 | `.omo/_knowledge/decisions/` | 架构决策记录 |
| 审计报告 | `.omo/_knowledge/audits/` | 各类审计结果 |
| 设计文档 | `.omo/_knowledge/design/` | 设计方案 |
| 管理文档 | `.omo/_knowledge/management/` | 管理指南 |
| 模式总结 | `.omo/_knowledge/patterns/` | 沉淀的模式 |
| 流程文档 | `.omo/_knowledge/process/` | 工作流程 |
| 参考文档 | `.omo/_knowledge/reference/` | 参考资料 |
| 总结文档 | `.omo/_knowledge/summaries/` | 各类总结 |
"""
    return overview

def generate_adr_section(adrs):
    # Group ADRs by prefix
    p7x = []
    str_series = []
    ecos_series = []
    gac_series = []
    arch_series = []
    ops_series = []
    other = []
    
    for adr in adrs:
        if adr.startswith("015") or adr.startswith("016") or adr.startswith("017") or adr.startswith("018") or adr.startswith("019"):
            p7x.append(adr)
        elif adr.startswith("STR-"):
            str_series.append(adr)
        elif "l0" in adr or "mof" in adr or "ecos" in adr:
            ecos_series.append(adr)
        elif "gac" in adr or "governance" in adr:
            gac_series.append(adr)
        elif "arch" in adr or "architecture" in adr or "bos" in adr:
            arch_series.append(adr)
        else:
            other.append(adr)
    
    section = """
---

## 按项目索引 ADR

### eCOS & 协议相关

| 类型 | 文件 | 主题 |
|------|------|------|
"""
    for adr in ecos_series[:10]:  # Show first 10
        section += f"| ADR | {adr} | {adr.replace('.md', '')} |\n"
    
    section += """
### GaC 治理相关

| 类型 | 文件 | 主题 |
|------|------|------|
"""
    for adr in gac_series[:10]:
        section += f"| ADR | {adr} | {adr.replace('.md', '')} |\n"
    
    section += """
### 架构演进相关

| 类型 | 文件 | 主题 |
|------|------|------|
"""
    for adr in arch_series[:10]:
        section += f"| ADR | {adr} | {adr.replace('.md', '')} |\n"
    
    section += """
### P7x 系列（声明/执行鸿沟）

| 类型 | 文件 | 主题 |
|------|------|------|
"""
    for adr in sorted(p7x):
        section += f"| ADR | {adr} | {adr.replace('.md', '')} |\n"
    
    section += """
### 战略路线图

| 类型 | 文件 | 主题 |
|------|------|------|
"""
    for adr in sorted(str_series):
        section += f"| ADR | {adr} | {adr.replace('.md', '')} |\n"
    
    return section

def generate_audit_section(audits):
    section = """
---

## 审计报告索引

| 审计类型 | 代表文件 |
|----------|---------|
"""
    # Show representative audits
    key_audits = [
        "2026-06-29-l0-ssot-m0-mof-alignment.md",
        "2026-07-02-p0-baseline-recovery-closeout.md",
        "2026-07-03-p74-workflow-solidification-closeout.md",
        "2026-07-02-system-comprehensive-audit.md",
    ]
    for audit in key_audits:
        if audit in audits:
            section += f"| {audit.split('-', 4)[-1].replace('.md', '')} | {audit} |\n"
    
    section += f"\n> 共 {len(audits)} 份审计报告，完整清单见 `.omo/_knowledge/audits/`\n"
    return section

def generate_patterns_section(patterns):
    section = """
---

## 模式总结

| 模式 | 文件 | 主题 |
|------|------|------|
"""
    for pattern in sorted(patterns):
        section += f"| {pattern.replace('.md', '')} | {pattern} | {pattern.replace('.md', '')} |\n"
    return section

def generate_footer():
    return """
---

## ADR 索引入口

完整的 ADR 索引请见: `.omo/_knowledge/decisions/INDEX.md`

---

## 说明

> 知识资产由脚本自动索引，最新内容以实际文件为准
> 
> 按主题分类和交叉引用由生成脚本动态构建
> 
> ADR 完整清单见 `.omo/_knowledge/decisions/INDEX.md`
"""

def main():
    generated_at = datetime.datetime.now(UTC).isoformat()
    
    categories = scan_knowledge_dir()
    
    content = TEMPLATE_HEADER.format(generated_at=generated_at)
    content += generate_overview(categories)
    content += generate_adr_section(categories.get("adrs", []))
    content += generate_audit_section(categories.get("audits", []))
    content += generate_patterns_section(categories.get("patterns", []))
    content += generate_footer()
    
    with open(INDEX_FILE, "w") as f:
        f.write(content)
    
    print(f"Generated: {INDEX_FILE}")

if __name__ == "__main__":
    main()
