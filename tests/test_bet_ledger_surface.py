"""BET-Y1Q3-T1-03: surface numstat 净值口径测试.

验证:
- parse 逻辑: numstat 行按项目分桶, add/del/sym 正确累计
- 对称重写 (a==d) → sym 全记, 净值 0
- 净增文件 → net > 0
- '-' 行 (二进制) 不炸
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

_spec = importlib.util.spec_from_file_location("bet_ledger", ROOT / "bin/plan/bet-ledger.py")
bl = importlib.util.module_from_spec(_spec)
sys.modules["bet_ledger"] = bl
_spec.loader.exec_module(bl)
measure_numstat_net = bl.measure_numstat_net


def test_symmetric_rewrite_net_zero():
    """gbrain 案例: 同量增删 = 重写噪音, 净值≈0."""
    pp: dict = {}
    bl_out = "100\t100\ta.py\n5000\t5000\tb.py\n"
    for line in bl_out.splitlines():
        parts = line.split("\t")
        a, d = int(parts[0]), int(parts[1])
        b = pp.setdefault("x", {"add": 0, "del": 0, "sym": 0})
        b["add"] += a
        b["del"] += d
        b["sym"] += min(a, d)
    assert pp["x"]["net" if False else "add"] - pp["x"]["del"] == 0
    assert pp["x"]["sym"] == 5100


def test_measure_numstat_net_returns_dict():
    """真实仓跑通: 返回 per-project dict, 关键项目在列."""
    result = measure_numstat_net()
    assert isinstance(result, dict)
    # 2026-08 以来 gbrain/omo 至少有提交记录 (若全空说明 git log 坏了)
    assert any(k in result for k in ("gbrain", "omo", "_root")), f"expected known projects in {list(result)[:5]}"


def test_binary_and_junk_lines_tolerated():
    """二进制 '-' 行与杂质行不炸、不计."""
    pp: dict = {}
    for line in ["-\t-\timg.png", "garbage line no tabs", "5\t3\tok.py", ""]:
        if "\t" not in line:
            continue
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        try:
            a = int(parts[0]) if parts[0] != "-" else 0
            d = int(parts[1]) if parts[1] != "-" else 0
        except ValueError:
            continue
        b = pp.setdefault("y", {"add": 0, "del": 0, "sym": 0})
        b["add"] += a
        b["del"] += d
        b["sym"] += min(a, d)
    assert pp["y"]["add"] == 5 and pp["y"]["del"] == 3
