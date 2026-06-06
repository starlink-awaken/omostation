"""Pytest 配置 — 确保 cockpit 包可导入。"""

import sys
from pathlib import Path

# 将 src/ 目录添加到 sys.path，使 `from cockpit import ...` 可工作
# 当 tests/ 位于 packages/cockpit/tests/ 时，cockpit 包 src 路径为:
# packages/cockpit/src/
_src = str(Path(__file__).resolve().parent.parent / "src")
if _src not in sys.path:
    sys.path.insert(0, _src)
