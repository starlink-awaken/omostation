"""健康摘要 CLI — 扫 FamilyShared → 应用规则 → 写 Markdown。"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path
from typing import Any

from minerva.health_summarizer.renderer import DEFAULT_OUTPUT, render, write_output
from minerva.health_summarizer.rules import ALL_RULES, HealthAlert
from minerva.health_summarizer.scanner import DEFAULT_PROFILE_DIR, scan_profiles


def _collect_alerts(profiles: Any, today: date, window_days: int) -> list[HealthAlert]:
    alerts: list[HealthAlert] = []
    for p in profiles:
        for rule in ALL_RULES:
            alerts.extend(rule(p, today, window_days))
    return alerts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="minerva.health_summarizer",
        description="扫描家庭健康档案，生成可读 Markdown 待办",
    )
    parser.add_argument(
        "--profiles-dir",
        type=Path,
        default=None,
        help=f"健康档案目录 (默认: {DEFAULT_PROFILE_DIR})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help=f"输出 Markdown 路径 (默认: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--window-days",
        type=int,
        default=60,
        help="疫苗/体检提醒窗口 (默认: 60)",
    )
    parser.add_argument(
        "--today",
        type=date.fromisoformat,
        default=None,
        help="覆盖今天 (YYYY-MM-DD)，用于测试",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只打印 Markdown 到 stdout，不写文件",
    )
    args = parser.parse_args(argv)

    today = args.today or date.today()
    profiles = scan_profiles(args.profiles_dir)
    if not profiles:
        print(
            "⚠️  无档案可扫描（FamilyShared/02.健康/档案/ 不存在或为空）",
            file=sys.stderr,
        )
        print(
            "💡 提示: 先跑 scripts/health_profile_demo.py 生成样例 JSON，再放一份到扫描目录",
            file=sys.stderr,
        )
        return 1

    alerts = _collect_alerts(profiles, today, args.window_days)
    content = render(alerts, today)

    if args.dry_run:
        print(content)
        return 0

    out = write_output(content, args.output)
    print(f"✅ 已写入 {len(alerts)} 条提醒 → {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
