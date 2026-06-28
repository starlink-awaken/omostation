#!/usr/bin/env python3
"""P94 R1: ADR drift 应用 — touch SUBDIR_MISSING 修复.

读 adr-drift-auto-fix --json 报告, 对 SUBDIR_MISSING 类型 touch 空文件
(父目录存在但文件缺失). 其它类型 (TEMPLATE/ASPIRATIONAL/REAL_BUG/TYPO) 不动.

用法:
  python3 bin/adr-drift-apply.py            # 应用 SUBDIR_MISSING 修复
  python3 bin/adr-drift-apply.py --json     # JSON 输出
  python3 bin/adr-drift-apply.py --dry-run  # 干跑 (不 touch)
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="P94 ADR drift apply (touch SUBDIR_MISSING)"
    )
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    parser.add_argument("--dry-run", action="store_true", help="干跑 (不 touch)")
    args = parser.parse_args()

    auto_fix = Path(__file__).parent / "adr-drift-auto-fix.py"
    applied: list[str] = []

    if auto_fix.exists():
        result = subprocess.run(
            ["python3", str(auto_fix), "--json"],
            capture_output=True,
            text=True,
        )
        try:
            report = json.loads(result.stdout) if result.stdout.strip() else {}
        except json.JSONDecodeError:
            report = {}

        # auto-fix 报告格式容错: issues 列表 or subdir_missing 列表
        issues = report.get("issues") or report.get("subdir_missing") or []
        for issue in issues:
            if isinstance(issue, dict):
                path_str = issue.get("path") or issue.get("file") or ""
                itype = issue.get("type", "")
            else:
                path_str = str(issue)
                itype = "SUBDIR_MISSING"

            if itype == "SUBDIR_MISSING" and path_str:
                p = Path(path_str)
                if not p.is_absolute():
                    continue  # 安全: 只 touch 绝对路径
                if not p.exists() and not args.dry_run:
                    try:
                        p.parent.mkdir(parents=True, exist_ok=True)
                        p.touch()
                        applied.append(str(p))
                    except OSError:
                        pass

    if args.json:
        print(json.dumps({"applied": applied, "count": len(applied)}))
    else:
        action = "would touch" if args.dry_run else "touched"
        print(f"✅ adr-drift-apply: {len(applied)} SUBDIR_MISSING {action}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
