#!/usr/bin/env python3
"""
文档索引自动生成脚本 (Phase 5 of DocGov)

功能:
1. 扫描仓库所有 .md 文件
2. 解析 frontmatter (type: ssot | derived | ephemeral)
3. 检查 SSOT 引用完整性
4. 输出 docs/generated/doc-inventory.md (SSOT 清单)
5. 检测孤立文档 (未被任何 SSOT 引用也未引用任何 SSOT)
6. 检测过期 ephemeral 文档

用法:
  python3 bin/ssot/generate-docs-index.py [--check] [--json]
  --check: 有异常时 exit 1 (用于 CI)
  --json:  额外输出 JSON 格式到 stdout

SSOT: docs/generated/doc-gov-framework.md (本脚本的行为由该框架定义)
"""

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

# --- 配置 ---
ROOT = Path(os.environ.get("WORKSPACE_ROOT", Path(__file__).resolve().parents[2]))
DOCS_DIR = ROOT / "docs"
GENERATED_DIR = DOCS_DIR / "generated"
OUTPUT_FILE = GENERATED_DIR / "doc-inventory.md"
OMO_DIR = ROOT / ".omo"

# 忽略路径
IGNORE_DIRS = {
    ".git",
    "node_modules",
    "__pycache__",
    ".venv",
    ".worktrees",
    "archive-*",
    "kos",
    ".pytest_cache",
    ".ruff_cache",
}
IGNORE_FILES = {"LAYER-INDEX.md"}  # 由其他脚本生成

SSOT_LIFESPAN_DAYS = 180
EPHEMERAL_LIFESPAN_DAYS = 90


def should_ignore(path: Path) -> bool:
    """检查路径是否在忽略列表中"""
    for part in path.parts:
        if part in IGNORE_DIRS:
            return True
        for pattern in IGNORE_DIRS:
            if "*" in pattern and part.startswith(pattern.rstrip("*")):
                return True
    return False


def parse_frontmatter(content: str) -> dict:
    """解析 YAML frontmatter (简化版，仅支持 key: value)"""
    fm = {}
    if not content.startswith("---"):
        return fm
    end = content.find("---", 3)
    if end == -1:
        return fm
    block = content[3:end].strip()
    for line in block.splitlines():
        if ":" in line:
            key, _, val = line.partition(":")
            fm[key.strip()] = val.strip().strip('"').strip("'")
    return fm


def scan_md_files() -> list[dict]:
    """扫描所有 .md 文件并提取元数据"""
    results = []
    for md in ROOT.rglob("*.md"):
        if should_ignore(md):
            continue
        rel = md.relative_to(ROOT)
        if rel.name in IGNORE_FILES:
            continue
        try:
            content = md.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        fm = parse_frontmatter(content)
        stat = md.stat()
        mtime = datetime.fromtimestamp(stat.st_mtime)
        results.append(
            {
                "path": str(rel),
                "type": fm.get("type", "untyped"),
                "source": fm.get("source", ""),
                "owner": fm.get("owner", ""),
                "status": fm.get("status", ""),
                "last_updated": fm.get("last_updated", ""),
                "mtime": mtime.isoformat()[:10],
                "size": stat.st_size,
                "lines": content.count("\n") + 1,
                "md5": hashlib.md5(content.encode()).hexdigest(),
            }
        )
    return results


def check_compliance(files: list[dict]) -> list[str]:
    """合规检查，返回问题列表"""
    issues = []
    now = datetime.now()

    for f in files:
        path = f["path"]

        # 1. SSOT 类型必须有 owner 和 last_updated
        if f["type"] == "ssot":
            if not f["owner"]:
                issues.append(f"[SSOT-NO-OWNER] {path}: SSOT 缺少 owner")
            if not f["last_updated"]:
                issues.append(f"[SSOT-NO-DATE] {path}: SSOT 缺少 last_updated")
            elif f["mtime"]:
                try:
                    mtime = datetime.strptime(f["mtime"], "%Y-%m-%d")
                    if (now - mtime).days > SSOT_LIFESPAN_DAYS:
                        issues.append(f"[SSOT-STALE] {path}: SSOT {f['mtime']} 未更新 (>{SSOT_LIFESPAN_DAYS}天)")
                except ValueError:
                    pass

        # 2. derived 类型必须有 source
        if f["type"] == "derived" and not f["source"]:
            issues.append(f"[DERIVED-NO-SOURCE] {path}: derived 类型缺少 source")

        # 3. ephemeral 过期检测
        if f["type"] == "ephemeral" and f["status"] != "archived":
            if f["last_updated"]:
                try:
                    updated = datetime.strptime(f["last_updated"], "%Y-%m-%d")
                    if (now - updated).days > EPHEMERAL_LIFESPAN_DAYS:
                        issues.append(f"[EPHEMERAL-EXPIRED] {path}: ephemeral 已过期 (>{EPHEMERAL_LIFESPAN_DAYS}天)")
                except ValueError:
                    pass

        # 4. 所有文档建议声明 type
        if f["type"] == "untyped":
            issues.append(f"[UNTYPED] {path}: 未声明 type (建议添加 frontmatter)")

    return issues


def find_orphans(files: list[dict]) -> list[str]:
    """查找孤立文档 (无 SSOT 引用关系)"""
    ssot_paths = {f["path"] for f in files if f["type"] == "ssot"}
    referenced = set()
    for f in files:
        if f["source"]:
            referenced.add(f["path"])
    orphans = []
    for f in files:
        if f["type"] == "untyped" and f["path"] not in ssot_paths and f["path"] not in referenced:
            orphans.append(f["path"])
    return orphans


def generate_inventory(files: list[dict], issues: list[str], orphans: list[str]) -> str:
    """生成 doc-inventory.md"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    ssots = [f for f in files if f["type"] == "ssot"]
    deriveds = [f for f in files if f["type"] == "derived"]
    ephemerals = [f for f in files if f["type"] == "ephemeral"]
    untyped = [f for f in files if f["type"] == "untyped"]

    lines = [
        "# 文档索引 (自动生成)",
        "",
        f"> 生成时间: {now}",
        f"> 总文档数: {len(files)}",
        "> 本文件由 `bin/ssot/generate-docs-index.py` 自动维护，不要手动编辑。",
        "",
        "## 统计",
        "",
        "| 类型 | 数量 |",
        "|------|------|",
        f"| SSOT | {len(ssots)} |",
        f"| derived | {len(deriveds)} |",
        f"| ephemeral | {len(ephemerals)} |",
        f"| untyped | {len(untyped)} |",
        "",
        "## SSOT 清单",
        "",
        "| 路径 | Owner | 最后更新 | 行数 |",
        "|------|-------|----------|------|",
    ]
    for f in sorted(ssots, key=lambda x: x["path"]):
        lines.append(f"| {f['path']} | {f['owner'] or '-'} | {f['mtime']} | {f['lines']} |")

    lines += ["", "## 派生文档", "", "| 路径 | Source | 同步时间 |", "|------|--------|----------|"]
    for f in sorted(deriveds, key=lambda x: x["path"]):
        lines.append(f"| {f['path']} | {f['source'] or '-'} | {f['last_updated'] or '-'} |")

    if ephemerals:
        lines += ["", "## 一次性文档", "", "| 路径 | 状态 | 创建日期 |", "|------|------|----------|"]
        for f in sorted(ephemerals, key=lambda x: x["path"]):
            lines.append(f"| {f['path']} | {f['status'] or '-'} | {f['last_updated'] or '-'} |")

    if issues:
        lines += ["", f"## 合规问题 ({len(issues)})", ""]
        for i in issues:
            lines.append(f"- {i}")

    if orphans:
        lines += ["", f"## 孤立文档 ({len(orphans)})", "", "> 未声明 type，也不引用任何 SSOT。", ""]
        for o in orphans[:50]:  # 限制输出量
            lines.append(f"- {o}")
        if len(orphans) > 50:
            lines.append(f"- ... 和另外 {len(orphans) - 50} 个文档")

    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description="文档索引生成器")
    parser.add_argument("--check", action="store_true", help="合规检查模式，有问题时 exit 1")
    parser.add_argument("--strict", action="store_true", help="严格模式 (UNTYPED 等软信号也计入失败)")
    parser.add_argument("--json", action="store_true", help="输出 JSON 格式")
    args = parser.parse_args()

    GENERATED_DIR.mkdir(parents=True, exist_ok=True)

    files = scan_md_files()
    issues = check_compliance(files)
    orphans = find_orphans(files)

    # 生成 Markdown 报告
    report = generate_inventory(files, issues, orphans)
    OUTPUT_FILE.write_text(report, encoding="utf-8")

    print(f"[doc-index] 扫描 {len(files)} 个 MD 文件 → {OUTPUT_FILE}")
    print(
        f"[doc-index] SSOT: {sum(1 for f in files if f['type'] == 'ssot')}, "
        f"derived: {sum(1 for f in files if f['type'] == 'derived')}, "
        f"ephemeral: {sum(1 for f in files if f['type'] == 'ephemeral')}, "
        f"untyped: {sum(1 for f in files if f['type'] == 'untyped')}"
    )
    print(f"[doc-index] 合规问题: {len(issues)}, 孤立文档: {len(orphans)}")

    if args.json:
        print(
            json.dumps(
                {
                    "total": len(files),
                    "by_type": {
                        "ssot": sum(1 for f in files if f["type"] == "ssot"),
                        "derived": sum(1 for f in files if f["type"] == "derived"),
                        "ephemeral": sum(1 for f in files if f["type"] == "ephemeral"),
                        "untyped": sum(1 for f in files if f["type"] == "untyped"),
                    },
                    "issues": issues,
                    "orphan_count": len(orphans),
                },
                ensure_ascii=False,
                indent=2,
            )
        )

    if args.check and issues:
        print(f"\n[doc-index] FAIL: {len(issues)} 个合规问题")
        sys.exit(1)

    if args.check:
        print("[doc-index] PASS")


if __name__ == "__main__":
    main()
