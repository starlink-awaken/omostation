"""Pytest 配置 — 确保 cockpit 包可导入。"""

import sys
from pathlib import Path

_root = Path(__file__).resolve().parent.parent

# 将 src/ 目录添加到 sys.path，使 `from cockpit import ...` 可工作
_src = str(_root / "src")
if _src not in sys.path:
    sys.path.insert(0, _src)

# 将项目根目录添加到 sys.path，使 `from web import ...` 可工作
_root_str = str(_root)
if _root_str not in sys.path:
    sys.path.insert(0, _root_str)
