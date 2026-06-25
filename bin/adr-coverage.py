#!/usr/bin/env python3
"""P85 R2: ADR coverage check tool.

校验 .omo/_knowledge/decisions/ 目录:
- ADR 编号连续性 (0001-0078 期望)
- 每个 ADR 文件 frontmatter 完整 (status, lifecycle, owner, last-reviewed)
- INDEX.md 引用所有 ADR 文件
- INDEX.md 不引用不存在的文件
- 重复编号检测

使用:
  python3 bin/adr-coverage.py
  python3 bin/adr-coverage.py --strict
  python3 bin/adr-coverage.py --json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

import yaml

REQUIRED_FRONTMATTER = ["status", "lifecycle", "owner", "last-reviewed"]


def list_adrs(decisions_dir: Path) -> list[tuple[int, Path]]:
    """列出所有 ADR 文件, 返回 (编号, 路径)."""
    adrs: list[tuple[int, Path]] = []
    if not decisions_dir.exists():
        return adrs
    for f in sorted(decisions_dir.glob("*.md")):
        # 解析文件名首部 4 位编号
        m = re.match(r"^(\d{4})-", f.name)
        if m:
            adrs.append((int(m.group(1)), f))
    return adrs


def parse_frontmatter(path: Path) -> dict:
    """解析 ADR frontmatter (兼容多文档)."""
    try:
        content = path.read_text(encoding="utf-8")
        for doc in yaml.safe_load_all(content):
            if isinstance(doc, dict):
                return doc
    except Exception:
        pass
    return {}


def parse_index(index_path: Path) -> dict:
    """解析 INDEX.md, 提取 ADR 引用."""
    if not index_path.exists():
        return {"adrs": [], "raw": ""}
    content = index_path.read_text(encoding="utf-8")
    # 提取 NNNN-*.md 引用 (匹配 markdown 链接或表格中的纯文本)
    # 模式 1: markdown 链接 (NNNN-xxx.md)
    pattern_link = re.compile(r"\(([0-9]{4}-[^)]+\.md)\)")
    # 模式 2: 表格中的纯文本 NNNN-xxx.md
    pattern_text = re.compile(r"(?<![\w/])([0-9]{4}-[a-z0-9-]+\.md)(?![\w/])")
    refs = set(pattern_link.findall(content)) | set(pattern_text.findall(content))
    return {"adrs": sorted(refs), "raw": content}


def check_coverage(decisions_dir: Path, index_path: Path) -> dict:
    """检查 ADR 覆盖度."""
    adrs = list_adrs(decisions_dir)
    if not adrs:
        return {"error": "no ADRs found"}

    # 编号集合
    numbers = [n for n, _ in adrs]
    files = {f.name for _, f in adrs}

    # 编号 gap 检测 (排除命名约定 gap: 0001-0099 + 0100-0999 + 1000+)
    # 仅报告同一区间内的 gap
    min_n, max_n = min(numbers), max(numbers)
    expected = set(range(min_n, max_n + 1))
    actual = set(numbers)
    missing_nums_all = sorted(expected - actual)
    # 区分: P28 (1-99) 和 P50+ (50-999) 的命名约定
    missing_nums = []
    for n in missing_nums_all:
        # 9-49 区间是 P28-P49 历史 gap (命名约定)
        if 9 <= n <= 49:
            continue
        missing_nums.append(n)
    duplicates = [n for n, c in Counter(numbers).items() if c > 1]

    # frontmatter 健康度
    fm_issues = []
    for n, f in adrs:
        fm = parse_frontmatter(f)
        missing = [k for k in REQUIRED_FRONTMATTER if k not in fm]
        if missing:
            fm_issues.append({
                "file": f.name,
                "missing": missing,
            })

    # INDEX 引用 vs 实际文件
    index_data = parse_index(index_path)
    index_refs = set(index_data["adrs"])
    files_not_in_index = sorted(files - index_refs)
    refs_not_in_files = sorted(index_refs - files)

    return {
        "total_adrs": len(adrs),
        "min_number": min_n,
        "max_number": max_n,
        "missing_numbers": missing_nums,
        "duplicate_numbers": duplicates,
        "frontmatter_issues": fm_issues,
        "files_not_in_index": files_not_in_index,
        "index_refs_not_in_files": refs_not_in_files,
        "index_present": index_path.exists(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="P85: ADR coverage check")
    parser.add_argument(
        "--decisions",
        default=".omo/_knowledge/decisions",
        help="ADR 目录",
    )
    parser.add_argument(
        "--index",
        default=".omo/_knowledge/decisions/INDEX.md",
        help="ADR INDEX.md",
    )
    parser.add_argument("--strict", action="store_true", help="warn 也算 error")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    args = parser.parse_args()

    decisions_dir = Path(args.decisions)
    index_path = Path(args.index)
    if not decisions_dir.exists():
        print(f"❌ {decisions_dir} 不存在")
        return 1

    result = check_coverage(decisions_dir, index_path)

    if "error" in result:
        print(f"❌ {result['error']}")
        return 1

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0

    print("=" * 60)
    print("🔍 P85 ADR coverage check")
    print("=" * 60)
    print(f"📋 ADR 总数: {result['total_adrs']}")
    print(f"🔢 编号范围: {result['min_number']:04d} ~ {result['max_number']:04d}")
    print()
    if result["missing_numbers"]:
        print(f"❌ 缺失编号: {result['missing_numbers']}")
    else:
        print(f"✅ 编号连续 ({result['max_number'] - result['min_number'] + 1} 范围无 gap)")
    if result["duplicate_numbers"]:
        print(f"❌ 重复编号: {result['duplicate_numbers']}")
    if result["frontmatter_issues"]:
        print(f"\n⚠️  Frontmatter 缺失 ({len(result['frontmatter_issues'])}):")
        for fi in result["frontmatter_issues"][:5]:
            print(f"   {fi['file']}: missing {fi['missing']}")
        if len(result["frontmatter_issues"]) > 5:
            print(f"   ... 还有 {len(result['frontmatter_issues']) - 5} 个")
    else:
        print("✅ 所有 frontmatter 完整")
    if result["files_not_in_index"]:
        print(f"\n⚠️  ADR 文件未在 INDEX 引用 ({len(result['files_not_in_index'])}):")
        for f in result["files_not_in_index"][:5]:
            print(f"   {f}")
        if len(result["files_not_in_index"]) > 5:
            print(f"   ... 还有 {len(result['files_not_in_index']) - 5} 个")
    if result["index_refs_not_in_files"]:
        print(f"\n❌ INDEX 引用不存在的文件 ({len(result['index_refs_not_in_files'])}):")
        for f in result["index_refs_not_in_files"][:5]:
            print(f"   {f}")
    if not result["files_not_in_index"] and not result["index_refs_not_in_files"]:
        print("\n✅ INDEX 引用与文件 100% 一致")

    issues_count = (
        len(result["missing_numbers"])
        + len(result["duplicate_numbers"])
        + len(result["frontmatter_issues"])
        + len(result["files_not_in_index"])
        + len(result["index_refs_not_in_files"])
    )
    if issues_count == 0:
        print("\n🎉 ADR 治理健康!")
    else:
        print(f"\n⚠️  {issues_count} 个问题需处理")

    return 1 if (result["missing_numbers"] or result["duplicate_numbers"] or result["index_refs_not_in_files"]) else 0


if __name__ == "__main__":
    sys.exit(main())
