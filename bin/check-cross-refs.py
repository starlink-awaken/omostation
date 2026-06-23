#!/usr/bin/env python3
"""P58 R1: 跨面引用一致性深度检查.

扫描 .omo/ 下所有 .md 文件的内部链接, 检测:
1. 相对路径引用 (./other.md, ../other.md, path/to.md)
2. 绝对路径引用 (.omo/xxx, docs/xxx)
3. 跨仓引用 (projects/*/xxx)
4. 引用目标是否存在

输出格式: file:broken_link 列表 + 修复建议
"""

from __future__ import annotations

import re
import sys
from pathlib import Path


def extract_links(content: str) -> list[tuple[str, int]]:
    """提取 markdown 链接 (text) 和纯路径引用."""
    links = []

    # Markdown 链接: [text](path)
    for m in re.finditer(r"\[([^\]]+)\]\(([^)]+)\)", content):
        path = m.group(2)
        if path.startswith(("http://", "https://", "#", "mailto:")):
            continue
        links.append((path, m.start()))

    # 纯路径引用 (常见于代码块或表格中): `path/to/file.md`
    for m in re.finditer(r"`([^`]*\.(?:md|yaml|json|py|sh))`", content):
        path = m.group(1)
        if "/" in path or path.startswith("."):
            if not path.startswith(("http", "#")):
                links.append((path, m.start()))

    return links


def resolve_link(source: Path, link: str, root: Path) -> Path | None:
    """解析链接到绝对路径, 返回 None 表示外部/无法解析."""
    # 跳过 URL 和锚点
    if link.startswith(("http://", "https://", "#", "mailto:")):
        return None

    # 跳过跨仓引用 (projects/X/...)
    if link.startswith("projects/"):
        return None

    # 跳过根仓外的绝对路径
    if link.startswith("/") and not str(root) in link:
        return None

    # 跳过 ~/Documents/ 引用 (外部)
    if link.startswith("~/"):
        return None

    # 根仓绝对路径 (以 .omo/ 或 docs/ 开头): 相对根解析, 不是相对源文件
    if link.startswith((".omo/", "docs/", "scripts/", "bin/", "tests/")):
        candidate = (root / link).resolve()
        return candidate

    # 相对路径 (./xxx, ../xxx, 或裸文件名)
    if link.startswith("./") or link.startswith("../"):
        candidate = (source.parent / link).resolve()
    else:
        # 裸文件名: 优先源目录, 其次根目录
        candidate = (source.parent / link).resolve()
        if not candidate.exists():
            candidate = (root / link).resolve()

    return candidate


def check_file(file: Path, root: Path) -> list[tuple[str, str]]:
    """检查单个文件的内部链接, 返回 (link, reason) 列表."""
    try:
        content = file.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return []

    issues = []
    for link, pos in extract_links(content):
        # 跳过代码块内的引用 (简单启发式: 行首有 4+ 空格)
        line_start = content.rfind("\n", 0, pos) + 1
        line_prefix = content[line_start:pos]
        if line_prefix.startswith("    ") or line_prefix.startswith("\t"):
            continue

        candidate = resolve_link(file, link, root)
        if candidate is None:
            continue

        if not candidate.exists():
            # 尝试 .md 后缀补全
            if not link.endswith(".md"):
                candidate_md = candidate.with_suffix(".md")
                if candidate_md.exists():
                    continue
            issues.append((link, f"target not found: {candidate.relative_to(root)}"))

    return issues


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    omo = root / ".omo"

    if not omo.exists():
        print(f"❌ .omo/ not found at {root}")
        return 1

    # 排除运行时产物: _delivery + tasks/registry/* (运行时快照)
    md_files = [
        f for f in omo.rglob("*.md")
        if "_delivery" not in f.parts
        and "registry" not in f.parts
    ]

    total_issues = 0
    files_with_issues = 0

    for f in md_files:
        issues = check_file(f, root)
        if issues:
            files_with_issues += 1
            total_issues += len(issues)
            rel = f.relative_to(root)
            for link, reason in issues[:5]:
                print(f"  {rel}: [{link}] → {reason}")
            if len(issues) > 5:
                print(f"  {rel}: ... and {len(issues) - 5} more")

    print()
    print(f"📊 总文件: {len(md_files)}")
    print(f"❌ 有问题文件: {files_with_issues}")
    print(f"❌ 总问题链接: {total_issues}")

    return 0 if total_issues == 0 else 1


if __name__ == "__main__":
    sys.exit(main())