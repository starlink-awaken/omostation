#!/usr/bin/env python3
"""CR-X1-EXTERNAL-AGENT-AUDIT: 外部 agent 接入审计 (advisory, **未实现**).

**这是占位桩, 不是实现。** 规则 CR-X1-EXTERNAL-AGENT-AUDIT 尚未落地真实检查:
缺的是判准本身 —— 「哪些面算外部 agent 接入」与「a2a-messages 这类直写
`.omo/state/` 的路径是否必须走 ingress」都还没有 owner 裁定 (governance_state
面有登记)。在判准落地前, 本文件**不提供任何强制力**。

因此它不做「永真的 print」: 退出码仍是 0 (gac-gate.yml 里对应步骤是
`continue-on-error: true` 的 advisory 步, 退出码不承重), 但 stdout 自报
`status: not_implemented`, 以免「恒 0」被下游读成「检查通过」。

顺带更正一条旧登记: `governance-checks.yaml` 的 X1 段里那条同族「agent 操作审计链」
规则曾把本文件写成 `source_ref` —— 那是**假门**, 已改指它的真实宿主（ecos 子模块里的
X1 审计链检查器, 见 `bin/gac/registry-alias-map.yaml` 的 X1 alias 组）。
"""

from __future__ import annotations

import json
import sys

CHECK_ID = "CR-X1-EXTERNAL-AGENT-AUDIT"


def main() -> int:
    print(json.dumps(
        {
            "check": CHECK_ID,
            "status": "not_implemented",
            "enforced": False,
            "reason": "external-agent attach criteria not defined; advisory placeholder only",
        },
        ensure_ascii=False,
    ))
    return 0


if __name__ == "__main__":
    sys.exit(main())
