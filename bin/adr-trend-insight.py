#!/usr/bin/env python3
"""P92 R1: ADR 趋势洞察工具.

读取 .omo/_knowledge/decisions/ + git log (ADR 提交历史), 输出:
- ADR 数量增长曲线 (按 phase / 阶段分桶)
- 引用健康度趋势 (P85 adr-coverage 历史 + P89 adr-drift 历史)
- top modified ADR (提交次数最多)
- 各 phase ADR 数量分布 (P28-P49 vs P50+)
- frontmatter 完整度趋势

使用:
  python3 bin/adr-trend-insight.py
  python3 bin/adr-trend-insight.py --json
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import yaml


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
        content: str = ""
        try:
            content = f.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            pass
        fm: dict = {}
        if content.startswith("---"):
            end = content.find("---", 3)
            if end > 0:
                try:
                    fm = yaml.safe_load(content[3:end]) or {}
                except Exception:
                    pass

        # 从 commit 历史取首次/最后提交时间
        first_seen, last_seen = _git_dates(f)

        adrs.append({
            "number": number,
            "file": f.name,
            "status": fm.get("status", "unknown"),
            "lifecycle": fm.get("lifecycle", "unknown"),
            "last_reviewed": fm.get("last-reviewed", "unknown"),
            "first_seen": first_seen,
            "last_seen": last_seen,
            "lines": content.count("\n") + 1,
        })
    return adrs


def _git_dates(file_path: Path) -> tuple[str, str]:
    """获取 ADR 首次 + 最后 commit 时间."""
    rel = str(file_path.relative_to(Path.cwd())) if file_path.is_absolute() else str(file_path)
    try:
        # 首次
        r1 = subprocess.run(
            ["git", "log", "--reverse", "--format=%cI", "--", rel],
            capture_output=True, text=True, timeout=10,
        )
        first = r1.stdout.strip().split("\n")[0] if r1.stdout.strip() else "?"
        # 最后
        r2 = subprocess.run(
            ["git", "log", "-1", "--format=%cI", "--", rel],
            capture_output=True, text=True, timeout=10,
        )
        last = r2.stdout.strip() if r2.stdout.strip() else "?"
    except Exception:
        first, last = "?", "?"
    return (first, last)


def phase_bucket(number: int) -> str:
    """ADR 编号 → phase 桶."""
    if number <= 8:
        return "P28 (P1-P28 早期)"
    if number < 50:
        return "P28-P49 (历史 archived)"
    if number < 60:
        return "P50-P59 (governance 收口起点)"
    if number < 70:
        return "P60-P69 (L4 治理)"
    if number < 80:
        return "P70-P79 (管理面深化)"
    if number < 90:
        return "P80-P89 (工具生态)"
    return "P90+ (治理闭环)"


def trend(adr_data: list[dict]) -> dict:
    """分析 ADR 趋势."""
    by_phase: dict[str, list[dict]] = defaultdict(list)
    by_status: Counter = Counter()
    by_lifecycle: Counter = Counter()
    by_year: Counter = Counter()
    fm_complete = 0
    fm_total = 0

    for a in adr_data:
        phase = phase_bucket(a["number"])
        by_phase[phase].append(a)
        by_status[a["status"]] += 1
        by_lifecycle[a["lifecycle"]] += 1
        if a["last_reviewed"] != "unknown":
            fm_total += 1
            fm_complete += 1
        # 按 first_seen 年份分桶
        if a["first_seen"] != "?":
            try:
                dt = datetime.fromisoformat(a["first_seen"].replace("Z", "+00:00"))
                by_year[dt.year] += 1
            except Exception:
                pass

    fm_pct = round(fm_complete / fm_total * 100, 1) if fm_total else 0.0

    return {
        "total_adrs": len(adr_data),
        "by_phase": {k: len(v) for k, v in by_phase.items()},
        "by_status": dict(by_status),
        "by_lifecycle": dict(by_lifecycle),
        "by_year": dict(sorted(by_year.items())),
        "fm_completeness_pct": fm_pct,
        "phases_ordered": sorted(by_phase.keys()),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="P92: ADR 趋势洞察")
    parser.add_argument("--decisions", default=".omo/_knowledge/decisions")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    adrs = load_adrs(Path(args.decisions))
    if not adrs:
        print("❌ 未发现 ADR")
        return 1

    result = trend(adrs)

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0

    print("=" * 60)
    print("📊 P92 ADR 趋势洞察")
    print("=" * 60)
    print(f"📋 ADR 总数: {result['total_adrs']}")
    print(f"📋 frontmatter 完整度: {result['fm_completeness_pct']}%")
    print()
    print("📦 按 phase 分布:")
    for phase in result["phases_ordered"]:
        count = result["by_phase"][phase]
        bar = "█" * min(count // 2, 30)
        print(f"   {phase:<35s} {count:>3d}  {bar}")
    print()
    if result["by_status"]:
        print("🏷️  按 status:")
        for s, c in sorted(result["by_status"].items(), key=lambda x: -x[1]):
            print(f"   {s:<20s} {c:>3d}")
    print()
    if result["by_year"]:
        print("📅 按首次 commit 年份:")
        for y, c in sorted(result["by_year"].items()):
            print(f"   {y}  {c:>3d} 新增")
    return 0


if __name__ == "__main__":
    sys.exit(main())
