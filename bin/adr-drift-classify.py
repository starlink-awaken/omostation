#!/usr/bin/env python3
"""P90 R1: ADR drift 自动归类工具.

读取 adr-drift-check 报告, 自动判断哪些 drift 是历史预期 (P28-P49 archived),
哪些是新增待修. 输出:
- 历史预期 issues: 标 archived (P28-P49 era 或 ADR 自身 status: archived)
- 新增 issues: 需关注
- 输出 markdown 报告 (可贴 governance 复盘)

使用:
  python3 bin/adr-drift-classify.py
  python3 bin/adr-drift-classify.py --json
  python3 bin/adr-drift-classify.py --report  # markdown
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import yaml

# P50+ 视为"近期" (governance 收口起点)
RECENT_ADR_THRESHOLD = 50


def load_adrs(decisions_dir: Path) -> list[dict]:
    """加载所有 ADR (含 frontmatter)."""
    adrs: list[dict] = []
    if not decisions_dir.exists():
        return adrs
    for f in sorted(decisions_dir.glob("*.md")):
        m = re.match(r"^(\d{4})-", f.name)
        if not m:
            continue
        number = int(m.group(1))
        # 解析 frontmatter (简化)
        try:
            content = f.read_text(encoding="utf-8", errors="ignore")
            fm = {}
            if content.startswith("---"):
                end = content.find("---", 3)
                if end > 0:
                    try:
                        fm = yaml.safe_load(content[3:end]) or {}
                    except Exception:
                        pass
        except Exception:
            fm = {}

        adrs.append({
            "number": number,
            "file": f.name,
            "status": fm.get("status", "unknown"),
            "lifecycle": fm.get("lifecycle", "unknown"),
        })
    return adrs


def classify(adr_drift_result: dict, adrs: list[dict]) -> dict:
    """将 adr-drift-check 结果归类: 历史预期 vs 新增待修."""
    adr_by_number = {a["number"]: a for a in adrs}

    historical = []
    new_issues = []

    for r in adr_drift_result.get("results", []):
        adr_number = r["adr_number"]
        adr_info = adr_by_number.get(adr_number, {})
        is_historical = (
            adr_number < RECENT_ADR_THRESHOLD
            or adr_info.get("status") == "archived"
            or adr_info.get("lifecycle") == "history"
        )

        for issue in r["issues"]:
            item = {
                "adr_number": adr_number,
                "file": r["file"],
                "issue_type": issue["type"],
                "msg": issue["msg"],
                "adr_status": adr_info.get("status", "unknown"),
            }
            if is_historical:
                historical.append(item)
            else:
                new_issues.append(item)

    by_type = Counter(i["issue_type"] for i in historical + new_issues)
    by_adr: dict[int, int] = defaultdict(int)
    for i in historical + new_issues:
        by_adr[i["adr_number"]] += 1

    return {
        "total_issues": len(historical) + len(new_issues),
        "historical_count": len(historical),
        "new_count": len(new_issues),
        "by_type": dict(by_type),
        "by_adr": dict(sorted(by_adr.items(), key=lambda x: -x[1])),
        "historical": historical[:20],  # 仅 sample
        "new_issues": new_issues,
        "checked_at": datetime.now().isoformat(),
    }


def render_markdown(result: dict) -> str:
    lines = [
        "# ADR Drift 归类报告 (P90 R1)",
        "",
        f"**总 issues**: {result['total_issues']}",
        f"**历史预期 (P28-P49/archived)**: {result['historical_count']}",
        f"**新增待修 (P50+)**: {result['new_count']}",
        "",
    ]
    if result["by_type"]:
        lines.append("## 按类型")
        lines.append("")
        for t, c in sorted(result["by_type"].items(), key=lambda x: -x[1]):
            lines.append(f"- **{t}**: {c}")
        lines.append("")
    if result["new_issues"]:
        lines.append(f"## 新增待修 issues ({len(result['new_issues'])})")
        lines.append("")
        for i in result["new_issues"][:20]:
            lines.append(f"- ADR-{i['adr_number']:04d} [{i['adr_status']}]: {i['msg']}")
        if len(result["new_issues"]) > 20:
            lines.append(f"- ... 还有 {len(result['new_issues']) - 20} 个")
        lines.append("")
    else:
        lines.append("🎉 **无新增待修 issues** (P50+ ADR 引用 100% 健康)")
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="P90: ADR drift 自动归类")
    parser.add_argument("--decisions", default=".omo/_knowledge/decisions")
    parser.add_argument("--root", default=".")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--report", action="store_true", help="markdown 输出")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if not (root / ".omo").exists():
        print(f"❌ {root} 不存在 .omo")
        return 1

    # 先跑 adr-drift-check
    import subprocess
    drift_bin = root / "bin" / "adr-drift-check.py"
    if not drift_bin.exists():
        print(f"❌ {drift_bin} 不存在")
        return 1

    r = subprocess.run(
        ["python3", str(drift_bin), "--json"],
        cwd=str(root), capture_output=True, text=True, timeout=60,
    )
    if r.returncode not in (0, 1):  # 工具允许 exit 0/1
        print(f"❌ adr-drift-check 失败: {r.stderr[:200]}")
        return 1
    try:
        adr_drift_result = json.loads(r.stdout)
    except json.JSONDecodeError as e:
        print(f"❌ JSON parse 失败: {e}")
        return 1

    # 加载 ADR 元数据
    adrs = load_adrs(root / args.decisions)
    result = classify(adr_drift_result, adrs)

    if args.report:
        print(render_markdown(result))
        return 0
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0

    print("=" * 60)
    print("🔍 P90 ADR drift 归类报告")
    print("=" * 60)
    print(f"📊 总 issues: {result['total_issues']}")
    print(f"📦 历史预期: {result['historical_count']} (P28-P49/archived)")
    print(f"🆕 新增待修: {result['new_count']} (P50+)")
    print()
    if result["by_type"]:
        print("按类型:")
        for t, c in sorted(result["by_type"].items(), key=lambda x: -x[1]):
            print(f"   {t}: {c}")
    print()
    if result["new_issues"]:
        print(f"🆕 新增待修 issues ({len(result['new_issues'])}):")
        for i in result["new_issues"][:10]:
            print(f"   ADR-{i['adr_number']:04d} [{i['adr_status']}]: {i['msg']}")
    else:
        print("🎉 P50+ ADR 引用 100% 健康!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
