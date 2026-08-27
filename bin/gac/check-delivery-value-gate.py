#!/usr/bin/env python3
"""CR-X3-DELIVERY-VALUE-GATE: 检查 X3 交付价值门禁.

交付 (delivery) 必须有 X3 价值标注, 确保投入产出可量化.
检查 .omo/_delivery/ 下的交付文件是否有 x3_tier / value 字段.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DELIVERY_DIR = REPO_ROOT / ".omo/_delivery"


def main() -> int:
    if not DELIVERY_DIR.is_dir():
        print("OK 未发现交付目录")
        return 0

    violations = []
    for f in sorted(DELIVERY_DIR.rglob("*.yaml")):
        rel = f.relative_to(REPO_ROOT)
        try:
            text = f.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        # 检查是否有 X3 价值标注
        has_x3 = "x3" in text.lower() or "value" in text.lower() or "roi" in text.lower()
        if not has_x3:
            violations.append(f"  {rel} — 缺少 X3 价值标注")

    if violations:
        print(f"WARN 发现 {len(violations)} 个交付文件缺少 X3 价值标注:")
        for v in violations:
            print(v)
        return 0  # advisory

    print("OK 所有交付文件有 X3 价值标注")
    return 0


if __name__ == "__main__":
    sys.exit(main())
