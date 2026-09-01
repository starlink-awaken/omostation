#!/usr/bin/env python3
"""CR-P77-6-2: 层级 fallback 测试覆盖检查 (advisory).

检查每级 fallback 是否有对应的测试覆盖。
当前为 advisory 模式，不阻断 CI。
"""

import sys


def main() -> int:
    print("[fallback-test-coverage] SKIP: advisory check (no fallback tests configured)")
    print("[fallback-test-coverage] TODO: 配置 fallback 测试后移入 blocking")
    return 0


if __name__ == "__main__":
    sys.exit(main())
