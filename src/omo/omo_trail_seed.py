"""omo trail seed — 写"trail 业务接入样例" step 到 .omo/_knowledge/omo-trail.jsonl (Round 19 P0).

目的:
  - 让 omo_trail 业务真落地 (之前 Round 12 P0 上线后 0 record, trail.jsonl 不存在)
  - re-init baseline 时 omo_trail 纳入 (drift=0, 但 schema 在 baseline 里注册)
  - 提供 5 条样例 step, 演示"未来 trail 业务接入"模式:
    actor=agent:laowang / cli / user, action=edit/exec/test/commit, target=file/command

用法:
    uv run --no-sync python -m omo.cli trail seed
    uv run --no-sync python -m omo.cli trail seed --log /tmp/test.jsonl  # 测试隔离

设计:
  - 5 条样例是"代表性"步骤, 反映老王 (Round 12-18) 工作模式:
    1. agent:laowang → edit → omo_lint.py
    2. agent:laowang → exec → pytest
    3. agent:laowang → test → omo_lint_schemas
    4. agent:laowang → commit → ebc1c41b
    5. agent:laowang → audit → omo_logs audit
  - 不写实际生产 record (那是 caller 的事, e.g. cockpit 启动时 omo trail record)
  - 本工具只"播种" — 让 schema 出现, baseline 守稳态

§11.6 P1-1 解锁:
  - "C (omo_trail baseline 纳入) — 等 trail 业务真上线"
  - 现在由本 seed 工具代为触发, 真业务上线后 caller 直接 omo trail record
"""
from __future__ import annotations

import argparse
from typing import Any

from omo.omo_trail import DEFAULT_TRAIL_PATH, record_step


# 5 条代表性 step (反映老王 Round 12-18 工作模式)
SEED_STEPS: list[dict[str, Any]] = [
    {"actor": "agent:laowang", "action": "edit", "target": "omo_lint.py", "status": "ok", "duration_ms": 450},
    {"actor": "agent:laowang", "action": "exec", "target": "pytest tests/test_omo_lint_schemas.py", "status": "ok", "duration_ms": 1520},
    {"actor": "agent:laowang", "action": "test", "target": "omo_lint_schemas (7/7 PASS)", "status": "ok", "duration_ms": 50},
    {"actor": "agent:laowang", "action": "commit", "target": "ebc1c41b (Round 18 P0)", "status": "ok", "duration_ms": 120},
    {"actor": "agent:laowang", "action": "audit", "target": "omo logs audit --baseline-check", "status": "ok", "duration_ms": 35},
]


def cmd_trail_seed(args: argparse.Namespace) -> int:
    """CLI: omo trail seed — 写 5 条样例 step."""
    written = 0
    for step in SEED_STEPS:
        record_step(log_path=args.log, **step)
        written += 1
    print(f"✅ trail seed 写入 {written} 条 step 到 {args.log}")
    print("   actor pattern: agent:laowang (代表老王工作流)")
    print("   真业务接入: caller 直接 omo trail record (e.g. cockpit 启动时)")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="omo trail seed",
        description="写 5 条代表性 step 到 omo-trail.jsonl (Round 19 P0 — 让 trail 业务真落地)",
    )
    parser.add_argument(
        "--log",
        type=str,
        default=str(DEFAULT_TRAIL_PATH),
        help=f"落点 .jsonl (默认: {DEFAULT_TRAIL_PATH})",
    )
    args = parser.parse_args(argv)
    return cmd_trail_seed(args)


if __name__ == "__main__":
    raise SystemExit(main())
