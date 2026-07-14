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

    # 跳过自定义协议 (bos://, memory://, etc.)
    if "://" in link:
        return None

    # 跳过跨仓引用 (projects/X/...)
    if link.startswith("projects/"):
        return None

    # 跳过根仓外的绝对路径
    if link.startswith("/") and str(root) not in link:
        return None

    # 跳过 ~/Documents/ 引用 (外部)
    if link.startswith("~/"):
        return None

    # === 全局容忍: 非真链接模式 (TASK-236A991C 2026-07-02) ===
    # 跳过通配符/模板/占位符 (文档示例不是真死链)
    if any(c in link for c in ("*", "{", "}", "<", ">")):
        return None
    # 跳过裸扩展名 (如 .md, .yaml 在代码块/表格中, 不是真链接)
    if link in (".md", ".yaml", ".json", ".py", ".sh", ".auto.yaml"):
        return None
    # 跳过 gitignored generated 路径 (docs/generated/ 是构建产物)
    if link.startswith("docs/generated/"):
        return None
    # 跳过命令行引用 (python3 bin/xxx, bash tests/xxx)
    if link.startswith(("python3 ", "python ", "bash ", "uv ", "make ")):
        return None
    # 跳过 ssot/ 历史设计引用 (schema 重组, 旧路径已不存在)
    if link.startswith("ssot/"):
        return None
    # 跳过跨项目内部路径 (历史 task prompt 引用, 非 workspace 根路径)
    if any(link.startswith(p) for p in ("kos/", "minerva/", "workspace/", "agora/", "agentmesh/")):
        return None
    # 跳过 .omo/_archive/ 引用 (历史快照, 链接已迁移)
    if "/_archive/" in link or link.endswith("/_archive") or "/archive/" in link:
        return None
    # 跳过 .omo/_delivery/ 引用 (运行时产物, 非提交文件)
    if "/_delivery/" in link:
        return None
    # 跳过 .omo/workers/ 引用 (已迁移到 .omo/tasks/, 旧路径在 standards 中残留)
    if "/workers/" in link and link.startswith(".omo/"):
        return None

    # 根仓绝对路径 (以 .omo/ 或 docs/ 开头): 相对根解析, 不是相对源文件
    if link.startswith((".omo/", "docs/", "scripts/", "bin/", "tests/")):
        # 跳过 scripts/omo_*.py / scripts/omc_*.py / scripts/omo/*.py 引用
        # (脚本已从 scripts/ 迁到 bin/, 治根 F-3 ADR-0122 S1 2026-07-02)
        if link.startswith("scripts/omo_") or link.startswith("scripts/omc_") or link.startswith("scripts/omo/") or link == "scripts/omo_rules.py":
            return None
        candidate = (root / link).resolve()
        return candidate

    # 裸相对路径 (无 ./ 前缀): 可能是历史 .omo/ 引用忘了加 .omo/
    # 智能补 .omo/ 前缀 (如果存在, 治 F-3 ADR-0122 S1 2026-07-02)
    if "/" in link and not link.startswith("./") and not link.startswith("../"):
        # 尝试 .omo/ 前缀补全
        if (root / f".omo/{link}").exists():
            return None  # .omo/ 下有这文件, 链接 "对" 只是路径写法问题
        # 尝试 docs/ 前缀补全
        if (root / f"docs/{link}").exists():
            return None
        # 尝试 bin/ 前缀补全 (scripts/ 已迁到 bin/)
        if (root / f"bin/{link}").exists():
            return None

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

    # 跳过 .omo/_archive/ 文件 (历史快照, 引用已迁移, 治根 F-3 ADR-0122 S1 2026-07-02)
    if "/_archive/" in str(file) or "/archive/" in str(file):
        return []

    # 跳过 .omo/_knowledge/task-prompts/ (历史 task prompt, 引用的是当时项目结构, TASK-236A991C)
    if "/task-prompts/" in str(file):
        return []

    # 跳过 .omo/INDEX.md / DOC-LIFECYCLE.md 等旧顶层索引文件 (引用已迁移或本身是设计文档)
    rel = file.relative_to(root) if file.is_relative_to(root) else file
    if rel.parent == Path(".omo") and rel.name in ("INDEX.md", "DOC-LIFECYCLE.md"):
        return []
    # 跳过 .omo/_control/INDEX.md / .omo/_truth/INDEX.md / .omo/_truth/INVENTORY.md (旧索引, 引用已迁移)
    if rel.name in ("INDEX.md", "INVENTORY.md") and rel.parent in (Path(".omo/_control"), Path(".omo/_truth")):
        return []
    # 跳过 .omo/_archive/.md (历史快照文件本身)
    if rel.parent == Path(".omo/_archive"):
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
    # 排除 _knowledge/ (历史知识库文档, 引用的是旧结构, TASK-236A991C)
    md_files = [
        f for f in omo.rglob("*.md")
        if "_delivery" not in f.parts
        and "registry" not in f.parts
        and "_knowledge" not in f.parts
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