#!/usr/bin/env python3
"""P81 R4: management 跨文件引用检查.

扫描 .omo/_knowledge/management/ (3 子目录 workflows/playbooks/guides) 内的文件,
检查跨文件引用 (md 链接 / 相对路径 / bos 路径).

输出:
- 总文件数 + 按子目录统计
- 跨子目录引用矩阵 (workflows → playbooks/guides 等)
- 死链 (引用了不存在的文件)
- 统计 + 报告

使用:
  python3 bin/management-cross-ref-check.py
  python3 bin/management-cross-ref-check.py --json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path


def scan_management(root: Path) -> dict:
    """扫描 management 目录."""
    mgr_dir = root / ".omo" / "_knowledge" / "management"
    if not mgr_dir.exists():
        return {}

    files_by_cat: dict[str, list[Path]] = defaultdict(list)
    all_files: list[Path] = []
    for sub in ["workflows", "playbooks", "guides"]:
        sd = mgr_dir / sub
        if sd.exists():
            for f in sorted(sd.glob("*.md")):
                files_by_cat[sub].append(f)
                all_files.append(f)
    # INDEX.md 单独
    index = mgr_dir / "INDEX.md"
    if index.exists():
        all_files.append(index)

    def category_of(f: Path) -> str:
        """解析文件所属子目录 (workflows/playbooks/guides/INDEX/other)."""
        try:
            rel = f.relative_to(mgr_dir)
            parts = rel.parts
            if len(parts) == 1 and parts[0] == "INDEX.md":
                return "INDEX"
            if len(parts) >= 2 and parts[0] in ("workflows", "playbooks", "guides"):
                return parts[0]
        except ValueError:
            pass
        return "other"

    # 提取 md 链接 (相对路径)
    link_pattern = re.compile(r"\]\(([^)]+\.md)(?:#[^)]*)?\)")
    refs_matrix: dict[tuple[str, str], int] = defaultdict(int)  # (from, to) -> count
    dead_links: list[tuple[Path, str, str]] = []  # (from_file, link, reason)
    external_links: list[tuple[Path, str]] = []  # (from_file, link) - 跨管理目录引用, 单独统计
    internal_resolved: list[tuple[Path, str]] = []  # (from_file, resolved_path) 内部解析成功

    # 文件 frontmatter status 缓存 (避免重复 IO)
    file_status: dict[Path, str] = {}

    def parse_status(f: Path) -> str:
        """从 frontmatter 解析 status (active/archived/etc)."""
        if f in file_status:
            return file_status[f]
        try:
            content = f.read_text(encoding="utf-8", errors="ignore")
            # 简化 frontmatter 解析
            if content.startswith("---"):
                end = content.find("---", 3)
                if end > 0:
                    fm = content[3:end]
                    for line in fm.splitlines():
                        if line.strip().startswith("status:"):
                            val = line.split(":", 1)[1].strip()
                            file_status[f] = val
                            return val
        except Exception:
            pass
        file_status[f] = "unknown"
        return "unknown"

    for f in all_files:
        try:
            content = f.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        # 找 md 链接
        for m in link_pattern.finditer(content):
            link = m.group(1)
            # 跳过 URL
            if link.startswith(("http://", "https://", "mailto:")):
                continue
            # 只检查 .md 文件
            if not link.endswith(".md"):
                continue
            # 提取目标文件名
            target = Path(link).name
            from_cat = category_of(f)
            # 解析链接: 绝对路径 (/Plans/x.md) 或跨域 (../../) → 外部
            is_external = link.startswith("/") or link.startswith(("..", "./"))
            if is_external:
                # 跨域引用: 不算死链, 单独记录
                external_links.append((f, link))
                # 但尝试解析一次, 看看目标是否真存在
                try:
                    if link.startswith("/"):
                        resolved = root / link.lstrip("/")
                    else:
                        resolved = (f.parent / link).resolve()
                    if not resolved.exists():
                        # 外部引用但目标不存在 → 算 dead
                        dead_links.append((f, link, f"external: {resolved} not found"))
                except Exception:
                    pass
                continue
            # 相对路径, 在同目录或子目录
            # 先看 target 是否在 files_by_cat 中
            to_cat = None
            for cat, cat_files in files_by_cat.items():
                if target in (cf.name for cf in cat_files):
                    to_cat = cat
                    break
            if to_cat:
                refs_matrix[(from_cat, to_cat)] += 1
                # 解析实际路径用于统计
                for cf in files_by_cat[to_cat]:
                    if cf.name == target:
                        internal_resolved.append((f, str(cf.relative_to(root))))
                        break
            else:
                dead_links.append((f, link, "target file not found"))

    return {
        "files_by_cat": {k: [f.name for f in v] for k, v in files_by_cat.items()},
        "counts": {k: len(v) for k, v in files_by_cat.items()},
        "index_present": index.exists(),
        "refs_matrix": {f"{k[0]}->{k[1]}": v for k, v in refs_matrix.items()},
        "dead_links": [(str(src), link, reason) for src, link, reason in dead_links],
        "dead_links_active": [
            (str(src), link, reason) for src, link, reason in dead_links if parse_status(src) != "archived"
        ],
        "dead_links_archived": [
            (str(src), link, reason) for src, link, reason in dead_links if parse_status(src) == "archived"
        ],
        "external_links": [(str(src), link) for src, link in external_links],
        "internal_resolved": [(str(src), path) for src, path in internal_resolved],
        "total_files": len(all_files),
        "totals": {
            "internal_resolved": len(internal_resolved),
            "external_links": len(external_links),
            "dead_links": len(dead_links),
            "dead_links_active": sum(1 for s, _, _ in dead_links if parse_status(s) != "archived"),
            "dead_links_archived": sum(1 for s, _, _ in dead_links if parse_status(s) == "archived"),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="P81: management 跨文件引用检查"
    )
    parser.add_argument("root", nargs="?", default=".", help="workspace root")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if not (root / ".omo").exists():
        print(f"❌ {root} 不存在 .omo")
        return 1

    result = scan_management(root)
    if not result:
        print("❌ management 目录不存在")
        return 1

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
        return 0

    print("=" * 60)
    print("📊 P81 management 跨文件引用检查 (P82 scope-aware)")
    print("=" * 60)
    print(f"📁 总文件: {result['total_files']}")
    print(f"📄 INDEX.md 存在: {result['index_present']}")
    print()
    print("按子目录:")
    for cat, count in result["counts"].items():
        print(f"  {cat:<15s} {count:>3d}")
    print()
    totals = result["totals"]
    print(f"🔗 内部引用 (已解析): {totals['internal_resolved']}")
    print(f"🌐 外部引用 (跨域):  {totals['external_links']}")
    print(f"❌ 死链 (目标不存在): {totals['dead_links']} = "
          f"active:{totals['dead_links_active']} + archived:{totals['dead_links_archived']}")
    print()
    print("跨子目录引用矩阵:")
    if result["refs_matrix"]:
        cats = list(result["counts"].keys()) + (["INDEX"] if result["index_present"] else [])
        print(f"  {'':12s}" + "".join(f"{c:>15s}" for c in cats))
        for from_cat in cats:
            row = f"  {from_cat:<12s}"
            for to_cat in cats:
                count = result["refs_matrix"].get(f"{from_cat}->{to_cat}", 0)
                row += f"{count:>15d}"
            print(row)
    else:
        print("  (无跨子目录引用)")
    print()
    if result["dead_links_active"]:
        print(f"\n❌ 死链 (active 文档, 需修复): {len(result['dead_links_active'])} 个")
        for src, link, reason in result["dead_links_active"][:10]:
            src_name = Path(src).name if isinstance(src, str) else src.name
            print(f"  {src_name}: {link} ({reason})")
        if len(result["dead_links_active"]) > 10:
            print(f"  ... 还有 {len(result['dead_links_active']) - 10} 个")
    if result["dead_links_archived"]:
        print(f"\n📦 死链 (archived 文档, 历史状态, 预期): {len(result['dead_links_archived'])} 个")
        for src, link, reason in result["dead_links_archived"][:5]:
            src_name = Path(src).name if isinstance(src, str) else src.name
            print(f"  {src_name}: {link}")
        if len(result["dead_links_archived"]) > 5:
            print(f"  ... 还有 {len(result['dead_links_archived']) - 5} 个")
    if not result["dead_links"]:
        print("\n✅ 无死链")
    print()
    if result["external_links"]:
        # 按 link 前缀分组统计
        ext_by_prefix: dict[str, int] = defaultdict(int)
        for _src, link in result["external_links"]:
            if link.startswith("/"):
                prefix = "/workspace-root"
            else:
                # 提取前两级
                parts = link.split("/")
                prefix = "/".join(parts[:2]) if len(parts) > 1 else parts[0]
            ext_by_prefix[prefix] += 1
        print("🌐 外部引用模式 (按前缀):")
        for prefix, count in sorted(ext_by_prefix.items(), key=lambda x: -x[1]):
            print(f"  {prefix:<40s} {count:>3d}")
    return 0


if __name__ == "__main__":
    sys.exit(main())