#!/usr/bin/env python3
"""
Check index drift - verify index files match actual content.

Owner: governance-team
Trigger: CI gate / manual verification
"""

import os
from pathlib import Path
import yaml
import sys

SCRIPT_DIR = Path(__file__).parent
WORKSPACE_ROOT = SCRIPT_DIR.parent.parent
PROJECT_REGISTRY = WORKSPACE_ROOT / "docs" / "project-registry.yaml"

def check_projects_index():
    """Check INDEX-PROJECTS.md matches project-registry.yaml"""
    print("Checking projects index...")
    
    with open(PROJECT_REGISTRY) as f:
        registry = yaml.safe_load(f)
    
    expected_projects = set()
    for name in registry["projects"].keys():
        if name != "mesh-router":
            expected_projects.add(name)
    
    # Read current index
    index_file = WORKSPACE_ROOT / "docs" / "INDEX-PROJECTS.md"
    if not index_file.exists():
        print("✗ INDEX-PROJECTS.md missing")
        return False
    
    content = index_file.read_text()
    found_projects = set()
    
    # Parse projects from index
    for name in expected_projects:
        if name in content:
            found_projects.add(name)
    
    missing = expected_projects - found_projects
    if missing:
        print(f"✗ Missing projects in index: {missing}")
        return False
    
    print("✓ Projects index OK")
    return True

def check_tools_index():
    """Check INDEX-TOOLS.md matches bin/ directory"""
    print("Checking tools index...")
    
    index_file = WORKSPACE_ROOT / "docs" / "INDEX-TOOLS.md"
    if not index_file.exists():
        print("✗ INDEX-TOOLS.md missing")
        return False
    
    # Check for key tools
    content = index_file.read_text()
    key_tools = [
        "gac-local-gate.py",
        "agent-workflow.py",
        "doc-ssot-lint.py",
        "adr-coverage.py",
    ]
    
    missing = []
    for tool in key_tools:
        if tool not in content:
            missing.append(tool)
    
    if missing:
        print(f"✗ Missing tools in index: {missing}")
        return False
    
    print("✓ Tools index OK")
    return True

def check_knowledge_index():
    """Check INDEX-KNOWLEDGE.md matches .omo/_knowledge/"""
    print("Checking knowledge index...")
    
    index_file = WORKSPACE_ROOT / "docs" / "INDEX-KNOWLEDGE.md"
    if not index_file.exists():
        print("✗ INDEX-KNOWLEDGE.md missing")
        return False
    
    content = index_file.read_text()
    
    # Check key categories are present
    categories = ["ADR", "审计报告", "模式总结"]
    missing = []
    for cat in categories:
        if cat not in content:
            missing.append(cat)
    
    if missing:
        print(f"✗ Missing categories in index: {missing}")
        return False
    
    print("✓ Knowledge index OK")
    return True

def check_agents_index():
    """Check INDEX-AGENTS.md matches .agents/skills/"""
    print("Checking agents index...")
    
    index_file = WORKSPACE_ROOT / "docs" / "INDEX-AGENTS.md"
    if not index_file.exists():
        print("✗ INDEX-AGENTS.md missing")
        return False
    
    content = index_file.read_text()
    
    # Check for key sections
    sections = ["Agent CLI", "项目级 Skills", "入门指南"]
    missing = []
    for section in sections:
        if section not in content:
            missing.append(section)
    
    if missing:
        print(f"✗ Missing sections in index: {missing}")
        return False
    
    print("✓ Agents index OK")
    return True

def check_system_index():
    """Check SYSTEM-INDEX.md exists and has key sections"""
    print("Checking system index...")
    
    index_file = WORKSPACE_ROOT / "docs" / "SYSTEM-INDEX.md"
    if not index_file.exists():
        print("✗ SYSTEM-INDEX.md missing")
        return False
    
    content = index_file.read_text()
    
    key_sections = [
        "快速开始",
        "层模型",
        "SSOT 导航",
        "分类索引",
    ]
    
    missing = []
    for section in key_sections:
        if section not in content:
            missing.append(section)
    
    if missing:
        print(f"✗ Missing sections in index: {missing}")
        return False
    
    print("✓ System index OK")
    return True

def main():
    print("=" * 60)
    print("INDEX DRIFT CHECK")
    print("=" * 60)
    print()
    
    checks = [
        check_system_index,
        check_projects_index,
        check_tools_index,
        check_knowledge_index,
        check_agents_index,
    ]
    
    results = []
    for check in checks:
        try:
            results.append(check())
            print()
        except Exception as e:
            print(f"✗ {check.__name__} failed: {e}")
            results.append(False)
            print()
    
    all_ok = all(results)
    
    print("=" * 60)
    if all_ok:
        print("✓ ALL INDEX CHECKS PASSED")
        print("=" * 60)
        return 0
    else:
        print("✗ INDEX DRIFT DETECTED")
        print()
        print("To regenerate indexes:")
        print("  python3 bin/ssot/gen-projects-index.py")
        print("  python3 bin/ssot/gen-tools-index.py")
        print("  python3 bin/ssot/gen-knowledge-index.py")
        print("  python3 bin/ssot/gen-agents-index.py")
        print("=" * 60)
        return 1

if __name__ == "__main__":
    sys.exit(main())
