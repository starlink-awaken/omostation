#!/usr/bin/env python3
"""
Generate INDEX-AGENTS.md from .agents/ scan.

Owner: governance-team
Trigger: Agent CLI 升级 / 新增 skill / 配置变更
"""

import os
from pathlib import Path
import datetime
from datetime import UTC

SCRIPT_DIR = Path(__file__).parent
WORKSPACE_ROOT = SCRIPT_DIR.parent.parent
INDEX_FILE = WORKSPACE_ROOT / "docs" / "INDEX-AGENTS.md"

TEMPLATE_HEADER = """# INDEX-AGENTS.md — Agent 能力索引

> **维护规则**
> - owner: governance-team
> - trigger: Agent CLI 升级 / 新增 skill / 配置变更
> - method: 脚本生成 (bin/ssot/gen-agents-index.py)
> - validation: skill 数与实际目录一致
> - status: active
> - created_at: 2026-07-14
> - generated_at: {generated_at}

---

"""

def _skill_frontmatter(skill_md: Path) -> dict:
    """Parse YAML frontmatter from SKILL.md (name/description)."""
    try:
        text = skill_md.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return {}
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    try:
        import yaml
        meta = yaml.safe_load(parts[1]) or {}
        return meta if isinstance(meta, dict) else {}
    except Exception:
        return {}


def scan_skills():
    """Return list of dicts: id, name, description (from frontmatter when present)."""
    skills_dir = WORKSPACE_ROOT / ".agents" / "skills"
    skills = []
    if skills_dir.exists():
        for d in sorted(skills_dir.iterdir()):
            skill_md = d / "SKILL.md"
            if d.is_dir() and skill_md.exists():
                meta = _skill_frontmatter(skill_md)
                desc = (meta.get("description") or "").strip().replace("\n", " ")
                if len(desc) > 120:
                    desc = desc[:117] + "..."
                skills.append({
                    "id": d.name,
                    "name": meta.get("name") or d.name,
                    "description": desc or d.name.replace("-", " "),
                })
    return skills

def generate_cli_section():
    return """## 本地 Agent CLI

| CLI | 配置位置 | 说明 |
|-----|---------|------|
| Claude Code | `~/.claude/` | 主要开发 Agent |
| Codex | `~/.codex/` | 代码专家 Agent |
| OpenCode | `~/.opencode/` | 开源协作 Agent |
| OMO | `projects/omo/` | 治理 Agent (项目级) |

"""

def generate_skills_section(skills):
    section = """
---

## 技能分布

| 位置 | 性质 |
|------|------|
| `.agents/skills/` | 项目级 Skills (工作区通用) |

"""
    
    if skills:
        section += """
---

## 项目级 Skills (.agents/skills/)

| Skill | 用途 | 触发场景 |
|-------|------|---------|
"""
        for skill in skills:
            if isinstance(skill, dict):
                sid = skill.get("id") or skill.get("name") or "?"
                desc = skill.get("description") or sid
                trigger = desc.split("。")[0].split(".")[0][:80]
                section += f"| `{sid}` | {desc} | {trigger} |\n"
            else:
                section += f"| {skill} | {skill.replace('-', ' ')} | 相关操作 |\n"

    section += """
### 外部 Agent 推荐包

见 [`docs/operations/external-agent-attach-card.md`](operations/external-agent-attach-card.md)：
`external-agent-attach` · `agent-onboarding` · `bos-service-discovery` · `project-governance` · `a2a-coordination`。

"""
    
    return section

def generate_guide_section():
    return """
---

## Agent 入门指南

### 新 Agent 设置步骤

1. **阅读入口文档**: `README.md` → `SYSTEM-INDEX.md`
2. **了解架构**: `ARCHITECTURE.md` → `PANORAMA.md`
3. **学习操作**: `AGENTS.md` → `CLAUDE.md`
4. **查看项目**: `INDEX-PROJECTS.md` → 目标项目文档
5. **查找工具**: `INDEX-TOOLS.md` → 可用工具目录
6. **查询历史**: `INDEX-KNOWLEDGE.md` → ADR/审计/模式

### 常见任务路径

| 任务 | 路径 |
|------|------|
| 开发新功能 | 项目 `AGENTS.md` → `INDEX-TOOLS.md` → 项目 `README.md` |
| 修复 bug | `AGENTS.md` §5 → 项目 `Makefile` → `INDEX-KNOWLEDGE.md` |
| 治理操作 | `CLAUDE.md` §0 → `agent-workflow.py` → `omo` CLI |
| 架构决策 | `ARCHITECTURE.md` → `INDEX-KNOWLEDGE.md` → ADR 目录 |

"""

def generate_footer():
    return """
---

## 说明

> Agent 配置和能力清单由脚本自动生成
> 
> 项目级 Skill 定义见 `.agents/skills/*/SKILL.md`
> 
> Agent 工作流使用见 `bin/agent-workflow.py --help`
"""

def main():
    generated_at = datetime.datetime.now(UTC).isoformat()
    
    skills = scan_skills()
    
    content = TEMPLATE_HEADER.format(generated_at=generated_at)
    content += generate_cli_section()
    content += generate_skills_section(skills)
    content += generate_guide_section()
    content += generate_footer()
    
    with open(INDEX_FILE, "w") as f:
        f.write(content)
    
    print(f"Generated: {INDEX_FILE}")

if __name__ == "__main__":
    main()
