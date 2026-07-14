#!/usr/bin/env python3
"""P93 R1: ADR drift 自动归类与修复建议工具.

读取 adr-drift-classify 报告, 自动判断每个 issue 类型:
- TEMPLATE: 路径含 YYYYMMDD/HHMM/HH 等占位符 (实际是模板示例, 不需修)
- ASPIRATIONAL: 路径根本不存在, 可能是设计阶段提及的"应该存在"路径
- SUBDIR_MISSING: 父目录存在但文件不存在 (可补空文件)
- REAL_BUG: 路径本应存在但消失, 需 ADR 修改或文件恢复
- TYPO: 路径接近已知文件 (typo 检查)

使用:
  python3 bin/adr/adr-drift-auto-fix.py            # 干跑
  python3 bin/adr/adr-drift-auto-fix.py --json
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

TEMPLATE_PATTERNS = re.compile(
    r"(YYYYMMDD|HHMM|YYYY-MM-DD|TBD|TODO|FIXME|XXX|<.*?>|\{.*?\})"
)
SUBDIR_PARENT_HINT = re.compile(r"src/(.*?)/")  # 找 src/ 父目录


def classify_issue(adr_number: int, msg: str, root: Path) -> dict:
    """分类单个 drift issue."""
    path = msg.replace("路径不存在: ", "").strip()

    # 1. 模板模式
    if TEMPLATE_PATTERNS.search(path):
        return {
            "type": "TEMPLATE",
            "reason": "路径含占位符 (YYYYMMDD/TBD/XXX), 是模板示例而非真实文件",
            "auto_fixable": True,
            "fix_action": "在 ADR 中标注 [TEMPLATE] 或加注释说明",
        }

    # 2. _log/ 动态生成路径
    if "/_log/" in path or "_log/" in path:
        return {
            "type": "TEMPLATE",
            "reason": "_log/ 目录是运行时生成, 不需静态存在",
            "auto_fixable": True,
            "fix_action": "在 ADR 中标注 [RUNTIME-GENERATED]",
        }

    # 3. 路径在 projects/* 目录但子目录不存在
    if path.startswith("projects/"):
        parts = path.split("/")
        if len(parts) >= 2:
            project_dir = root / parts[0] / parts[1]
            if not project_dir.exists():
                return {
                    "type": "ASPIRATIONAL",
                    "reason": f"projects/{parts[1]}/ 整个子项目不存在, 是设计规划未落地",
                    "auto_fixable": False,
                    "fix_action": "ADR 应删除该引用, 或 P93+ 创建 stub",
                }

    # 4. 父目录存在但文件不存在
    full = root / path
    parent = full.parent
    if parent.exists() and not full.exists():
        return {
            "type": "SUBDIR_MISSING",
            "reason": f"父目录 {parent.relative_to(root)} 存在, 文件缺失",
            "auto_fixable": True,
            "fix_action": f"touch '{path}' 占位 (或 ADR 修正引用)",
        }

    # 5. 接近已知文件 (typo 检查)
    if "." in path.split("/")[-1]:
        basename = path.split("/")[-1]
        # 简单 typo: 字符相似度
        similar = _find_similar(root, basename, threshold=0.85)
        if similar:
            return {
                "type": "TYPO",
                "reason": f"可能 typo, 实际文件: {similar}",
                "auto_fixable": True,
                "fix_action": f"ADR 中 '{basename}' → '{similar}'",
            }

    # 6. 默认: 真 bug
    return {
        "type": "REAL_BUG",
        "reason": "路径本应存在但消失, 需修复 ADR 或文件",
        "auto_fixable": False,
        "fix_action": "人工 review",
    }


def _find_similar(root: Path, basename: str, threshold: float = 0.85) -> str | None:
    """找相似文件名 (Levenshtein 简化版)."""
    if len(basename) < 4:
        return None
    best: str | None = None
    best_score = 0.0
    for f in root.rglob("*"):
        if not f.is_file() or f.name == basename:
            continue
        score = _similarity(f.name, basename)
        if score > best_score and score >= threshold:
            best_score = score
            best = str(f.relative_to(root))
    return best


def _similarity(a: str, b: str) -> float:
    """简化 Levenshtein 相似度 (字符集合 Jaccard)."""
    if not a or not b:
        return 0.0
    set_a = set(a.lower())
    set_b = set(b.lower())
    if not set_a or not set_b:
        return 0.0
    intersection = set_a & set_b
    union = set_a | set_b
    return len(intersection) / len(union)


def main() -> int:
    parser = argparse.ArgumentParser(description="P93: ADR drift 自动归类")
    parser.add_argument("--root", default=".")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if not (root / ".omo").exists():
        print(f"❌ {root} 不存在 .omo")
        return 1

    # 调用 adr-drift-classify 拿 JSON
    drift_bin = root / "bin" / "adr" / "adr-drift-classify.py"
    if not drift_bin.exists():
        print(f"❌ {drift_bin} 不存在")
        return 1
    r = subprocess.run(
        ["python3", str(drift_bin), "--json"],
        cwd=str(root), capture_output=True, text=True, timeout=60,
    )
    if r.returncode not in (0, 1):
        print(f"❌ adr-drift-classify 失败: {r.stderr[:200]}")
        return 1
    try:
        classify_result = json.loads(r.stdout)
    except json.JSONDecodeError as e:
        print(f"❌ JSON parse: {e}")
        return 1

    # 分类
    classified: list[dict] = []
    for issue in classify_result.get("new_issues", []):
        cls = classify_issue(issue["adr_number"], issue["msg"], root)
        classified.append({
            **issue,
            "classification": cls,
        })

    # 统计
    by_type = Counter(c["classification"]["type"] for c in classified)
    auto_fixable = sum(1 for c in classified if c["classification"]["auto_fixable"])

    result = {
        "total_p50_issues": len(classified),
        "by_type": dict(by_type),
        "auto_fixable_count": auto_fixable,
        "items": classified,
    }

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0

    print("=" * 60)
    print("🔧 P93 ADR drift 自动归类")
    print("=" * 60)
    print(f"📊 P50+ 总 issues: {result['total_p50_issues']}")
    print(f"🛠️  可自动修复: {result['auto_fixable_count']}")
    print()
    print("按类型:")
    for t, c in sorted(by_type.items(), key=lambda x: -x[1]):
        print(f"   {t:<18s} {c:>3d}")
    print()
    # 按类型分组列出
    for t in sorted(by_type.keys(), key=lambda x: -by_type[x]):
        items = [c for c in classified if c["classification"]["type"] == t]
        print(f"📦 {t} ({len(items)}):")
        for item in items[:5]:
            print(f"   ADR-{item['adr_number']:04d} [{item['adr_status']}]: {item['msg'][:60]}")
            print(f"     💡 {item['classification']['fix_action']}")
        if len(items) > 5:
            print(f"   ... 还有 {len(items) - 5} 个")
    return 0


if __name__ == "__main__":
    sys.exit(main())
