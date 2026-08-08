#!/usr/bin/env python3
"""CR-P77-FALLBACK-TEST: 检查层级 fallback 测试覆盖.

P77-6-2: 每级 fallback 都必须有测试证明不崩溃.
检查 tests/ 下是否有 fallback 相关测试.
"""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TEST_FALLBACK_MARKERS = ["fallback", "retry", "backup", "resilience", "circuit_breaker", "timeout"]


def main() -> int:
    test_files = []
    for d in ["tests", "projects"]:
        d_path = REPO / d
        if not d_path.is_dir():
            continue
        for f in d_path.rglob("test_*.py"):
            text = f.read_text(encoding="utf-8", errors="ignore")
            for marker in TEST_FALLBACK_MARKERS:
                if marker in text.lower():
                    test_files.append(f.relative_to(REPO))
                    break

    if not test_files:
        print("WARN 未发现 fallback 相关测试 (P77-6-2)")
        return 0  # advisory

    print(f"OK 发现 {len(test_files)} 个 fallback 相关测试文件")
    return 0


if __name__ == "__main__":
    sys.exit(main())
