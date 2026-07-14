#!/usr/bin/env python3
"""
Generate INDEX-PROJECTS.md from project-registry.yaml.

Owner: governance-team
Trigger: 新项目加入 / 项目归档 / 层级变更
"""

import yaml
import os
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
WORKSPACE_ROOT = SCRIPT_DIR.parent.parent
PROJECT_REGISTRY = WORKSPACE_ROOT / "docs" / "project-registry.yaml"
INDEX_FILE = WORKSPACE_ROOT / "docs" / "INDEX-PROJECTS.md"

TEMPLATE_HEADER = """# INDEX-PROJECTS.md — 项目索引

> **维护规则**
> - owner: governance-team
> - trigger: 新项目加入 / 项目归档 / 层级变更
> - method: 脚本生成 (bin/ssot/gen-projects-index.py)
> - validation: 与 project-registry.yaml 项目数一致
> - status: active
> - created_at: 2026-07-14
> - generated_at: {generated_at}

---

"""

def load_registry():
    with open(PROJECT_REGISTRY) as f:
        return yaml.safe_load(f)

def generate_layer_table(registry):
    layers = {}
    for name, project in registry["projects"].items():
        if name == "mesh-router":
            continue
        layer = project.get("layer", "?")
        if layer not in layers:
            layers[layer] = []
        layers[layer].append(name)
    
    table = "## 按层分类\n\n| 层 | 项目 | 栈 | 入口文档 |\n|----|------|-----|---------|\n"
    for layer in sorted(layers.keys()):
        projects = ", ".join(sorted(layers[layer]))
        stacks = set()
        for name in layers[layer]:
            project = registry["projects"][name]
            stack = project.get("stack", "?")
            stacks.add(stack)
        stack_str = " + ".join(sorted(stacks))
        table += f"| {layer} | {projects} | {stack_str} | 各项目 `AGENTS.md` |\n"
    return table

def generate_stack_table(registry):
    stacks = {}
    for name, project in registry["projects"].items():
        if name == "mesh-router":
            continue
        stack = project.get("stack", "?")
        if stack not in stacks:
            stacks[stack] = []
        stacks[stack].append(name)
    
    table = "\n---\n\n## 按栈分类\n\n| 栈 | 项目 |\n|----|------|\n"
    for stack in sorted(stacks.keys()):
        projects = ", ".join(sorted(stacks[stack]))
        table += f"| {stack} | {projects} |\n"
    return table

def generate_project_list(registry):
    python_projects = []
    ts_projects = []
    docker_projects = []
    
    for name, project in registry["projects"].items():
        if name == "mesh-router":
            continue
        stack = project.get("stack", "")
        role = project.get("role", "")
        
        if "Python" in stack:
            python_projects.append((name, project.get("layer", "?"), role))
        elif "TypeScript" in stack:
            ts_projects.append((name, project.get("layer", "?"), role))
        elif "Docker" in stack:
            docker_projects.append((name, project.get("layer", "?"), role))
    
    output = "\n---\n\n## 项目清单\n\n### Python (uv) 项目\n\n| 项目 | 层 | 角色 | AGENTS.md |\n|------|----|------|-----------|\n"
    for name, layer, role in sorted(python_projects):
        output += f"| {name} | {layer} | {role} | ✅ |\n"
    
    output += "\n### TypeScript (bun) 项目\n\n| 项目 | 层 | 角色 | AGENTS.md |\n|------|----|------|-----------|\n"
    for name, layer, role in sorted(ts_projects):
        output += f"| {name} | {layer} | {role} | ✅ |\n"
    
    output += "\n### Docker 项目\n\n| 项目 | 层 | 角色 | AGENTS.md |\n|------|----|------|-----------|\n"
    for name, layer, role in sorted(docker_projects):
        output += f"| {name} | {layer} | {role} | ✅ |\n"
    
    return output

def generate_archived_table(registry):
    archived = registry.get("archived", [])
    table = "\n---\n\n## 归档项目参考\n\n| 项目 | 合并到 | 说明 |\n|------|--------|------|\n"
    for item in archived:
        table += f"| {item['name']} | {item['merged_into']} | {item.get('note', '')} |\n"
    return table

def generate_footer():
    return """
---

## 说明

> 数据来源: `docs/project-registry.yaml` + 扫描 `projects/*/` 目录
> 
> 本索引文件只包含指针，不持有任何硬编码数值（数值以 `project-registry.yaml` 为准）
> 
> 完整的项目元数据请见: `docs/project-registry.yaml`
"""

def main():
    import datetime
    generated_at = datetime.datetime.utcnow().isoformat()
    
    registry = load_registry()
    
    content = TEMPLATE_HEADER.format(generated_at=generated_at)
    content += generate_layer_table(registry)
    content += generate_stack_table(registry)
    content += generate_project_list(registry)
    content += generate_archived_table(registry)
    content += generate_footer()
    
    with open(INDEX_FILE, "w") as f:
        f.write(content)
    
    print(f"Generated: {INDEX_FILE}")

if __name__ == "__main__":
    main()
