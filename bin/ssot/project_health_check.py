#!/usr/bin/env python3
"""project_health_check.py — 任意项目治理健康快照（Wave 3 外部接入）

依据 .omo/_knowledge/patterns/doc-l0-mof-mapping-governance.md Wave 3:
让 MOF 治理框架可对任意项目复用 —— 参数化项目路径, 跑治理健康快照
(frontmatter 覆盖率 / ADR 数量 / 文档规模), 验证框架包可移植性。

用法:
    python3 bin/ssot/project_health_check.py --project projects/kairon
"""

import argparse
import sys
from pathlib import Path


def frontmatter_coverage(project_dir: str) -> dict:
    """统计项目 frontmatter 覆盖率。"""
    root = Path(project_dir)
    md_files = list(root.rglob("*.md"))
    total = len(md_files)
    with_fm = 0
    for f in md_files:
        try:
            c = f.read_text(encoding="utf-8", errors="ignore")[:4000]
            if c.startswith("---"):
                with_fm += 1
        except OSError:
            continue
    coverage = with_fm * 100 // max(total, 1) if total else 0
    return {"total": total, "with_frontmatter": with_fm, "coverage_pct": coverage}


def health_snapshot(project_dir: str) -> dict:
    """项目治理健康快照：frontmatter + ADR 数量 + 文档规模。"""
    root = Path(project_dir)
    frontmatter = frontmatter_coverage(project_dir)
    adr_files = list((root / ".omo" / "_knowledge" / "decisions").glob("*.md")) \
        if (root / ".omo" / "_knowledge" / "decisions").exists() else []
    return {
        "frontmatter": frontmatter,
        "adr_count": len(adr_files),
        "md_files": frontmatter["total"],
        "has_omo": (root / ".omo").exists(),
        "has_standards": (root / ".omo" / "standards").exists(),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--project", required=True, help="项目相对路径 (如 projects/kairon)")
    ap.add_argument("--json", action="store_true", help="JSON 输出")
    args = ap.parse_args()
    root = Path(__file__).resolve().parents[2] / args.project
    if not root.exists():
        print(f"[FAIL] 项目不存在: {root}", file=sys.stderr)
        return 1
    snap = health_snapshot(str(root))
    if args.json:
        import json

        print(json.dumps(snap, ensure_ascii=False, indent=1))
        return 0
    f = snap["frontmatter"]
    print(f"项目: {args.project}")
    print(f"  MD 文件: {f['total']} | frontmatter: {f['with_frontmatter']} ({f['coverage_pct']}%)")
    print(f"  ADR: {snap['adr_count']} | .omo: {snap['has_omo']} | standards: {snap['has_standards']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
