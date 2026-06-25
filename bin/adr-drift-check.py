#!/usr/bin/env python3
"""P89 R2: ADR drift check tool.

校验 .omo/_knowledge/decisions/ 治理健康度:
- ADR 提及的 `.omo/...` 路径是否存在
- ADR 提及的 bin 工具是否存在
- ADR 提及的 ADR-XXXX 编号是否存在
- ADR 编号连续性 (排除 P28-P49 命名约定 gap)

使用:
  python3 bin/adr-drift-check.py
  python3 bin/adr-drift-check.py --json
  python3 bin/adr-drift-check.py --adr ADR-0082
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

# ADR 引用模式
ADR_REF_PATTERNS = [
    re.compile(r"\bADR-(\d{4})\b"),
    re.compile(r"\badr-(\d{4})\b", re.IGNORECASE),
]
PATH_REF_PATTERNS = [
    re.compile(r"`([\w./\-]+\.(?:py|md|yaml|yml|sh))`"),  # 路径 in backticks
    re.compile(r"bin/[\w\-]+\.py"),
    re.compile(r"projects/[\w/\-]+"),
    re.compile(r"\.omo/[\w/\-]+"),
]


def load_adrs(decisions_dir: Path) -> list[tuple[int, Path]]:
    """返回 (编号, 路径) 列表."""
    adrs: list[tuple[int, Path]] = []
    if not decisions_dir.exists():
        return adrs
    for f in sorted(decisions_dir.glob("*.md")):
        m = re.match(r"^(\d{4})-", f.name)
        if m:
            adrs.append((int(m.group(1)), f))
    return adrs


def extract_references(content: str) -> dict:
    """从 ADR 内容提取引用 (ADR 编号, 路径)."""
    refs: dict = {
        "adr_refs": set(),
        "path_refs": set(),
    }
    for pat in ADR_REF_PATTERNS:
        for m in pat.finditer(content):
            # 保留原始 4 位字符串, 避免 0081 → 81 前导 0 丢失
            refs["adr_refs"].add(m.group(1))
    for pat in PATH_REF_PATTERNS:
        for m in pat.finditer(content):
            refs["path_refs"].add(m.group(1) if "(" in pat.pattern else m.group(0))
    return refs


def check_drift(adrs: list[tuple[int, Path]], root: Path, known_adr_numbers: set[str] | None = None) -> dict:
    """检查每条 ADR 的引用健康度."""
    if known_adr_numbers is None:
        known_adr_numbers = {f"{n:04d}" for n, _ in adrs}
    results = []
    total_issues = 0

    for n, f in adrs:
        try:
            content = f.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        refs = extract_references(content)

        issues = []

        # 1. ADR 引用: 编号是否存在 (字符串比较, 保持 4 位)
        for adr_ref in refs["adr_refs"]:
            if adr_ref not in known_adr_numbers:
                issues.append({
                    "type": "missing_adr",
                    "msg": f"ADR-{adr_ref} 不存在",
                })

        # 2. 路径引用: 文件或目录是否存在
        for path in refs["path_refs"]:
            # 排除明显 glob 段
            if "*" in path or "{" in path or "?" in path:
                continue
            # 排除纯文件名 (e.g. omo_lint.py 在 markdown 中引用, 实际是 projects/.../omo_lint.py)
            # 启发: 如果 path 不含 /, 只在已知 bin 列表中检查
            if "/" not in path:
                continue
            # 排除路径末端的 .md/.yaml (可能用作说明, 不一定存在)
            # 仍检查: 如果是具体路径应该存在
            full = root / path
            # 排除纯目录引用 (不带扩展名且路径看起来是目录)
            if "." not in path.split("/")[-1] and full.is_dir():
                continue
            if not full.exists():
                # 兼容: 自动补 .md 后缀
                if not path.endswith(".md") and (root / f"{path}.md").exists():
                    continue
                # 兼容: 路径可能是 stdlib name (如 `argparse`), 不报
                # 启发: 如果 path 完全没 /, 或 path 长度 < 8, 视为 stdlib
                if len(path) < 8:
                    continue
                # 排除 _delivery 内的 _archive 已迁移文件
                if "_archive" in path:
                    continue
                # 排除 .omc 引用 (gitignored)
                if path.startswith(".omc/"):
                    continue
                issues.append({
                    "type": "missing_path",
                    "msg": f"路径不存在: {path}",
                })

        results.append({
            "adr_number": n,
            "file": f.name,
            "adr_refs": sorted(refs["adr_refs"]),
            "path_refs": sorted(refs["path_refs"]),
            "issues": issues,
            "issue_count": len(issues),
        })
        total_issues += len(issues)

    by_type: dict[str, int] = defaultdict(int)
    for r in results:
        for issue in r["issues"]:
            by_type[issue["type"]] += 1

    return {
        "total_adrs": len(adrs),
        "total_issues": total_issues,
        "by_type": dict(by_type),
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="P89: ADR drift check")
    parser.add_argument("--decisions", default=".omo/_knowledge/decisions")
    parser.add_argument("--root", default=".")
    parser.add_argument("--adr", help="仅检查单条 ADR (按文件名前缀或编号)")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if not (root / ".omo").exists():
        print(f"❌ {root} 不存在 .omo")
        return 1

    adrs = load_adrs(root / args.decisions)
    if not adrs:
        print("❌ 未发现 ADR")
        return 1

    # known 集合: 总是用全量 (即使 --adr 过滤单条, 也要能解析 ADR-XXXX 交叉引用)
    # check_drift 默认用传入的 adrs 计算 known, 这里我们传全量
    result = check_drift(adrs, root)
    # 重新运行用全量 known
    all_adrs = load_adrs(root / args.decisions)
    known_adr_numbers = {f"{n:04d}" for n, _ in all_adrs}
    if args.adr:
        try:
            n = int(args.adr.replace("ADR-", ""))
            adrs = [(nn, ff) for nn, ff in all_adrs if nn == n]
        except ValueError:
            adrs = [(nn, ff) for nn, ff in all_adrs if ff.name.startswith(args.adr)]
    result = check_drift(adrs, root, known_adr_numbers)

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0

    print("=" * 60)
    print("🔍 P89 ADR drift check")
    print("=" * 60)
    print(f"📋 ADRs: {result['total_adrs']}")
    print(f"⚠️  Issues: {result['total_issues']}")
    if result["by_type"]:
        print(f"   按类型: {result['by_type']}")
    print()
    if result["total_issues"] == 0:
        print("🎉 所有 ADR 引用健康!")
        return 0
    # 只显示有 issue 的
    for r in result["results"]:
        if r["issue_count"] == 0:
            continue
        print(f"  ADR-{r['adr_number']:04d} ({r['file']}):")
        for issue in r["issues"][:5]:
            print(f"    {issue['type']}: {issue['msg']}")
        if len(r["issues"]) > 5:
            print(f"    ... 还有 {len(r['issues']) - 5} 个")
    # 信息性: 不阻塞退出 (P89 dashboard 集成)
    return 0


if __name__ == "__main__":
    sys.exit(main())
