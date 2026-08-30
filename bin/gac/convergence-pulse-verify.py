#!/usr/bin/env python3
"""convergence-pulse-weekly workflow 的 verification 硬门。

独立脚本替代 v1 的内联 python（引号嵌套在部分 shell 下转义失败）。
当日采集器能跑且 schema 正确即 PASS。
"""

from __future__ import annotations

import sys
from datetime import date
from importlib import util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = util.spec_from_file_location("convergence_pulse_verify", ROOT / "bin/gac/convergence-pulse.py")
assert spec and spec.loader
module = util.module_from_spec(spec)
spec.loader.exec_module(module)

pulse = module.collect_pulse(since=date.today(), until=date.today())
ok = pulse["schema"] == "governance.convergence-pulse.v1"
print(f"convergence-pulse-verify: {'PASS' if ok else 'FAIL'} schema={pulse['schema']}")
sys.exit(0 if ok else 1)
