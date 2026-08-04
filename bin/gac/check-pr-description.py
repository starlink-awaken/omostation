#!/usr/bin/env python3
"""CR-PR-DESCRIPTION-NON-EMPTY: 校验 PR 描述非空.

在 gac-gate CI 中作为 pre-flight 步骤运行, 确保 PR 描述包含变更动机与验证.
仅在 PR 触发时生效 (push to main 不检查).

用法:
    python3 bin/gac/check-pr-description.py
    # 读取 GITHUB_EVENT_NAME + GITHUB_EVENT_PATH 环境变量

退出码:
    0: PR 描述非空或非 PR 事件
    1: PR 描述为空
"""
from __future__ import annotations

import json
import os
import sys


def main() -> int:
    event_name = os.environ.get("GITHUB_EVENT_NAME", "")
    event_path = os.environ.get("GITHUB_EVENT_PATH", "")

    # 非 PR 事件跳过 (push to main, workflow_dispatch 等)
    if event_name not in ("pull_request", "pull_request_target"):
        return 0

    if not event_path or not os.path.isfile(event_path):
        print("[check-pr-description] ⚠️  GITHUB_EVENT_PATH 不可用, 跳过")
        return 0

    with open(event_path) as f:
        event = json.load(f)

    pr_body = (event.get("pull_request") or {}).get("body") or ""
    pr_title = (event.get("pull_request") or {}).get("title") or ""

    if not pr_body.strip():
        print(
            "[check-pr-description] ❌ PR 描述为空 — 请添加变更动机与验证说明"
        )
        print(f"  PR 标题: {pr_title[:80]}")
        print(
            "  建议: 在 PR 描述中说明 what/why/how, 以及本地验证结果"
        )
        return 1

    print(f"[check-pr-description] ✅ PR 描述非空 ({len(pr_body.strip())} 字符)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
