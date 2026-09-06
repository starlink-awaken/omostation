#!/usr/bin/env python3
"""
机制 10 (2026-09-05): 文档数字漂移检测 — 文档中硬编码的数字 vs SSOT 生成值对比.

校验规则:
  - "N 子模块" / "N 项目" / "N projects" 等数字声明
  - 对比 .gitmodules 中实际的子模块数量
  - 对比 registry.yaml 中实际注册数量

使用:
  python bin/gac/check-doc-numbers.py                  # advisory
  python bin/gac/check-doc-numbers.py --fail-on-drift  # 漂移时 exit 1

退出码:
  0 = 一致
  1 = 发现漂移
"""

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path


def get_actual_submodule_count(root: str) -> int:
    """从 .gitmodules 获取实际子模块数量."""
    gitmodules = os.path.join(root, ".gitmodules")
    if not os.path.exists(gitmodules):
        return 0
    result = subprocess.run(
        ["git", "config", "--file", gitmodules, "--get-regexp", "path"],
        capture_output=True, text=True,
    )
    return len([l for l in result.stdout.splitlines() if l.strip()])


def get_actual_project_count(root: str) -> int:
    """从 registry.yaml 获取实际项目数量."""
    registry_path = os.path.join(root, "docs", "project-registry.yaml")
    if not os.path.exists(registry_path):
        return 0
    import yaml
    with open(registry_path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return len([k for k, v in data.items() if isinstance(v, dict) and v.get("submodule")])


SSOT_DOCS = {
    "AGENTS.md",
    "CLAUDE.md",
    "ARCHITECTURE.md",
    "GOVERNANCE.md",
    "README.md",
    "docs/CLI-REFERENCE.md",
    "docs/project-registry.yaml",
}

def is_ssot_doc(rel_path: str) -> bool:
    """判断是否为 SSOT 文档."""
    return rel_path in SSOT_DOCS


DOC_PATTERNS = [
    # 匹配 "N 子模块" / "N 个项目" / "N projects" 等
    (re.compile(r'(\d+)\s*个子模块'), 'submodule_count'),
    (re.compile(r'(\d+)\s*个项目'), 'project_count'),
    (re.compile(r'(\d+)\s*projects?', re.IGNORECASE), 'project_count'),
]


def scan_docs(root: str, actual_submodules: int, actual_projects: int) -> list[dict]:
    """扫描 SSOT 文档中的硬编码数字."""
    drifts = []

    # 检查根目录 SSOT 文档
    for name in ["AGENTS.md", "CLAUDE.md", "ARCHITECTURE.md", "GOVERNANCE.md", "README.md"]:
        doc_path = os.path.join(root, name)
        if os.path.exists(doc_path):
            _check_file(doc_path, name, root, actual_submodules, actual_projects, drifts)

    # 检查 docs/ SSOT 文档
    docs_dir = os.path.join(root, "docs")
    if os.path.exists(docs_dir):
        for md_file in Path(docs_dir).rglob("*.md"):
            rel_path = str(md_file.relative_to(root))
            if is_ssot_doc(rel_path):
                _check_file(str(md_file), rel_path, root, actual_submodules, actual_projects, drifts)

    return drifts


def _check_file(doc_path: str, rel_path: str, root: str,
                actual_submodules: int, actual_projects: int,
                drifts: list[dict]) -> None:
    """检查单个文件的数字漂移."""
    content = Path(doc_path).read_text(encoding="utf-8")
    for pattern, kind in DOC_PATTERNS:
        for match in pattern.finditer(content):
            declared_num = int(match.group(1))
            actual = actual_submodules if kind == 'submodule_count' else actual_projects
            if declared_num != actual:
                line_num = content[:match.start()].count('\n') + 1
                drifts.append({
                    "file": rel_path,
                    "line": line_num,
                    "declared": declared_num,
                    "actual": actual,
                    "kind": kind,
                    "context": content.splitlines()[line_num - 1].strip() if line_num <= len(content.splitlines()) else "",
                })


def main() -> int:
    parser = argparse.ArgumentParser(description="文档数字漂移检测")
    parser.add_argument("--fail-on-drift", action="store_true")
    args = parser.parse_args()

    root = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()

    actual_submodules = get_actual_submodule_count(root)
    actual_projects = get_actual_project_count(root)
    drifts = scan_docs(root, actual_submodules, actual_projects)

    if drifts:
        print(f"❌ 发现 {len(drifts)} 处文档数字漂移 "
              f"(实际: 子模块={actual_submodules}, 项目={actual_projects}):",
              file=sys.stderr)
        for d in drifts:
            print(f"   {d['file']}:{d['line']} 声明={d['declared']} 实际={d['actual']} "
                  f"[{d['kind']}]  \"{d['context']}\"", file=sys.stderr)
        if args.fail_on_drift:
            return 1
        return 0

    print(f"✅ 文档数字一致 (子模块={actual_submodules}, 项目={actual_projects})",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
