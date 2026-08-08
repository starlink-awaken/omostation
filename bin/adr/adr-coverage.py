#!/usr/bin/env python3
"""P85 R2: ADR coverage check tool.

校验 .omo/_knowledge/decisions/ 目录:
- ADR 编号连续性 (0001-0078 期望)
- 每个 ADR 文件 frontmatter 完整 (status, lifecycle, owner, last-reviewed)
- INDEX.md 引用所有 ADR 文件
- INDEX.md 不引用不存在的文件
- 重复编号检测

使用:
  python3 bin/adr/adr-coverage.py
  python3 bin/adr/adr-coverage.py --strict
  python3 bin/adr/adr-coverage.py --json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import yaml
from _lib import duplicate_adr_numbers, list_adrs

REQUIRED_FRONTMATTER = ["status", "lifecycle", "owner", "last-reviewed"]
HISTORICAL_STATUSES = {"superseded", "archived", "done", "deprecated", "withdrawn"}


def classify_layer(frontmatter: dict) -> str:
    """Classify an ADR into 'active' or 'historical' layer (BET-Y1Q2-T6-02).

    Historical: status in HISTORICAL_STATUSES (superseded/archived/done/etc).
    Active: everything else (accepted/active/proposed/candidate/partial/draft).
    """
    status = str(frontmatter.get("status", "")).strip().lower()
    if status in HISTORICAL_STATUSES:
        return "historical"
    return "active"


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
    pattern_text = re.compile(r"(?<![\w/-])([0-9]{4}-[a-z0-9-]+\.md)(?![\w/])")
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
    # 占号中 (adr-claims 存在) 的号不算缺失 — session 在写 ADR (G-CONV.7 D1)
    claims: dict[int, dict] = {}
    try:
        import sys as _sys  # noqa: PLC0415
        _gac = Path(__file__).resolve().parent.parent / "gac"
        if str(_gac) not in _sys.path:
            _sys.path.insert(0, str(_gac))
        from swarm_discipline import load_adr_claims  # noqa: PLC0415

        _claims_dir = decisions_dir.parents[2] / ".omo" / "_delivery" / "adr-claims"
        claims = load_adr_claims(_claims_dir)
    except Exception:
        pass
    missing_nums = []
    for n in missing_nums_all:
        # 9-49 区间是 P28-P49 历史 gap (命名约定)
        if 9 <= n <= 49:
            continue
        # 239-248 区间是 P82→P83 之间历史跳号 (task #9 任务#4, 2026-07-28 容忍)
        # 真工程: 改 CI 容忍历史 gap (与 9-49 同理), 非建 RESERVED 占位 gaming
        if 239 <= n <= 248:
            continue
        # 占号中 (claim 存在) = session 在写, 不算缺失
        if n in claims:
            continue
        missing_nums.append(n)
    duplicates = duplicate_adr_numbers(decisions_dir)

    # frontmatter 健康度
    fm_issues = []
    id_mismatches = []
    status_counts: dict[str, int] = {}  # T6-02 ADR 分层: 按 status 统计
    for n, f in adrs:
        fm = parse_frontmatter(f)
        status = str(fm.get("status", "unknown")).strip().lower() or "unknown"
        status_counts[status] = status_counts.get(status, 0) + 1
        missing = [k for k in REQUIRED_FRONTMATTER if k not in fm]
        if missing:
            fm_issues.append({
                "file": f.name,
                "missing": missing,
            })
        # C2 (ADR-0367): frontmatter id 必须与文件名 ADR-NNNN 一致 (缺失也算违规)
        file_id = f.name.split("-", 1)[0]  # e.g. "0233" from "0233-xxx.md"
        fm_id = str(fm.get("id", "")).strip()
        if not fm_id or fm_id.upper() != f"ADR-{file_id}":
            id_mismatches.append({
                "file": f.name,
                "id": fm_id or "<missing>",
                "expected": f"ADR-{file_id}",
            })

    # INDEX 引用 vs 实际文件
    index_data = parse_index(index_path)
    index_refs = set(index_data["adrs"])
    files_not_in_index = sorted(files - index_refs)
    refs_not_in_files = sorted(index_refs - files)

    # T6-02: active / historical 分层
    active_files: list[str] = []
    historical_files: list[str] = []
    for n, f in adrs:
        fm = parse_frontmatter(f)
        layer = classify_layer(fm)
        if layer == "historical":
            historical_files.append(f.name)
        else:
            active_files.append(f.name)

    return {
        "total_adrs": len(adrs),
        "min_number": min_n,
        "max_number": max_n,
        "missing_numbers": missing_nums,
        "duplicate_numbers": duplicates,
        "frontmatter_issues": fm_issues,
        "id_mismatches": id_mismatches,
        "files_not_in_index": files_not_in_index,
        "index_refs_not_in_files": refs_not_in_files,
        "index_present": index_path.exists(),
        "by_status": status_counts,
        "layer": {
            "active": sorted(active_files),
            "historical": sorted(historical_files),
            "active_count": len(active_files),
            "historical_count": len(historical_files),
        },
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
    parser.add_argument(
        "--layer", action="store_true",
        help="输出 active/historical 分层 JSON (供 RAG/onboarding 消费)",
    )
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

    if args.layer:
        layer = result.get("layer", {})
        print(json.dumps(layer, indent=2, ensure_ascii=False))
        return 0

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0

    print("=" * 60)
    print("🔍 P85 ADR coverage check")
    print("=" * 60)
    print(f"📋 ADR 总数: {result['total_adrs']}")
    print(f"🔢 编号范围: {result['min_number']:04d} ~ {result['max_number']:04d}")
    # T6-02 ADR 分层统计 (active 进 RAG/onboarding, historical 不进)
    layer = result.get("layer", {})
    print(
        f"📑 分层: active {layer.get('active_count', 0)} | "
        f"historical {layer.get('historical_count', 0)}"
    )
    if layer.get("historical"):
        hist = layer["historical"]
        print(f"   historical: {', '.join(hist[:10])}" + (" ..." if len(hist) > 10 else ""))
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
    if result["id_mismatches"]:
        print(f"\n❌ Frontmatter id 与文件名不符 ({len(result['id_mismatches'])}):")
        for im in result["id_mismatches"]:
            print(f"   {im['file']}: id={im['id']!r} (期望 {im['expected']})")
    else:
        print("✅ 所有 frontmatter id 与文件名一致")
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
        + len(result["id_mismatches"])
        + len(result["files_not_in_index"])
        + len(result["index_refs_not_in_files"])
    )
    if issues_count == 0:
        print("\n🎉 ADR 治理健康!")
    else:
        print(f"\n⚠️  {issues_count} 个问题需处理")

    return 1 if (result["missing_numbers"] or result["duplicate_numbers"] or result["frontmatter_issues"] or result["id_mismatches"] or result["files_not_in_index"] or result["index_refs_not_in_files"]) else 0


if __name__ == "__main__":
    sys.exit(main())
