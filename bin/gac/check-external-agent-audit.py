#!/usr/bin/env python3
"""CR-X1-EXTERNAL-AGENT-AUDIT: 外部 agent 审计检查 (advisory).

检查外部 agent 接入是否注册 MCP 入口 + 审计链。
当前为 advisory 模式，不阻断 CI。
"""

import sys


def main() -> int:
    print("[external-agent-audit] SKIP: advisory check (no external agents registered)")
    print("[external-agent-audit] TODO: 接入外部 agent 后移入 blocking")
    return 0


if __name__ == "__main__":
    sys.exit(main())
