#!/usr/bin/env python3
"""T10-154/155/156 closeout — minimal status flip.

These BETs were minimal placeholder entries added by #3605 alongside the
script delivery in #3578. The actual code/tests are already merged.
We just need: add done_when, verify, write_surfaces, flip status to done.
"""
import sys
from pathlib import Path

import yaml

LEDGER = Path("docs/plans/3y-bet-ledger.yaml")
DATA = yaml.safe_load(LEDGER.read_text(encoding="utf-8"))

NOW = "2026-09-12"

DEFINITIONS = {
    "BET-Y1Q4-T10-154": {
        "done_when": [
            "check-diff-lifecycle.py 在 CI 阻断孤立未应用代码 diff (合并 commit 但未被吸收的 patch)",
            "tests/unit/test_diff_lifecycle.py 覆盖 4 种孤儿 diff 场景",
            "pre-commit hook 集成 (gac-local-gate 串入)",
        ],
        "verify": [
            {"cmd": "uv run pytest tests/unit/test_diff_lifecycle.py -q", "expect": "exit 0"},
            {"cmd": "python3 bin/gac/check-diff-lifecycle.py", "expect": "exit 0"},
            {"cmd": "make gac-local-gate", "expect": "exit 0"},
        ],
        "write_surfaces": [
            "bin/gac/check-diff-lifecycle.py",
            "tests/unit/test_diff_lifecycle.py",
        ],
        "circuit_breaker": "任何导致 gac-local-gate fail 的回归立即停止.",
        "goal": "扫描 workspace 中的 .patch/.diff 文件, 检测其中包含的 commit 是否已被后续 merge 覆盖, 防止孤儿 diff 长期占用仓库空间.",
        "track": "T10-MATURITY",
        "workflow": "bet-execution",
        "human_gate": False,
        "risk_level": "L2",
        "retro": "required",
        "value_indicator_policy": False,
        "depends_on": [],
    },
    "BET-Y1Q4-T10-155": {
        "done_when": [
            "check-diff-debt.py 在 PR diff 中检测新增 FIXME/HACK/TODO 并与 base 对比",
            "tests/unit/test_diff_debt.py 覆盖 5 种债务继承场景",
            "warning budget 5 个 / PR, 超过阻断合并",
        ],
        "verify": [
            {"cmd": "uv run pytest tests/unit/test_diff_debt.py -q", "expect": "exit 0"},
            {"cmd": "python3 bin/gac/check-diff-debt.py", "expect": "exit 0"},
            {"cmd": "make gac-local-gate", "expect": "exit 0"},
        ],
        "write_surfaces": [
            "bin/gac/check-diff-debt.py",
            "tests/unit/test_diff_debt.py",
        ],
        "circuit_breaker": "任何导致 gac-local-gate fail 的回归立即停止.",
        "goal": "扫描当前分支 diff 中新增的 FIXME/HACK/TODO 标记, 检查对应代码在 base 中是否已存在未解决的债务, 防止新增技术债.",
        "track": "T10-MATURITY",
        "workflow": "bet-execution",
        "human_gate": False,
        "risk_level": "L2",
        "retro": "required",
        "value_indicator_policy": False,
        "depends_on": [],
    },
    "BET-Y1Q4-T10-156": {
        "done_when": [
            "check-diff-growth.py 计算 PR diff LOC 增量, 超过阈值标记 warning",
            "tests/unit/test_diff_growth.py 覆盖 +/- 阈值边界",
            "与 check-bin-quota-diff 互补: 后者按脚本计数, 前者按代码行数",
        ],
        "verify": [
            {"cmd": "uv run pytest tests/unit/test_diff_growth.py -q", "expect": "exit 0"},
            {"cmd": "python3 bin/gac/check-diff-growth.py", "expect": "exit 0"},
            {"cmd": "make gac-local-gate", "expect": "exit 0"},
        ],
        "write_surfaces": [
            "bin/gac/check-diff-growth.py",
            "tests/unit/test_diff_growth.py",
        ],
        "circuit_breaker": "任何导致 gac-local-gate fail 的回归立即停止.",
        "goal": "计算当前分支相对 base 分支的代码增长量, 超过阈值时标记 warning, 防止单 PR 代码膨胀.",
        "track": "T10-MATURITY",
        "workflow": "bet-execution",
        "human_gate": False,
        "risk_level": "L2",
        "retro": "required",
        "value_indicator_policy": False,
        "depends_on": [],
    },
}


def find_and_replace(bet_id: str, spec: dict) -> bool:
    """Update existing minimal entry with full done-state fields."""
    for b in DATA["bets"]:
        if b.get("id") == bet_id:
            b.update(spec)
            b["status"] = "done"
            b["done_at"] = NOW
            return True
    return False


for bet_id, spec in DEFINITIONS.items():
    if not find_and_replace(bet_id, spec):
        print(f"WARNING: {bet_id} not found", file=sys.stderr)
        sys.exit(1)
    print(f"OK: {bet_id} → done")

DATA["meta"]["total_bets"] = len(DATA["bets"])

LEDGER.write_text(
    yaml.safe_dump(DATA, allow_unicode=True, sort_keys=False, default_flow_style=False),
    encoding="utf-8",
)
print(f"Wrote ledger: {len(DATA['bets'])} total bets")
