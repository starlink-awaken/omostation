"""下划线命名版别名 — 与 bin/gac/zhixing-host-sync.py 同源.

`zhixing-panel-sync.py ensure` 末段通过 `importlib.util.spec_from_file_location`
按模块名加载 `zhixing_host_sync`（下划线版），把生产代码与现有 `zhixing-host-sync.py`
（连字符版 CLI 入口）耦合起来:

  - `module.status(dashboard_dir, host_dir)` → 与现有 status() 同语义（带参数）
  - `module.check(...)` → 与现有 check() 同语义
  - `module.capture(...)` / `module.restore(...)` → 同上

该别名只重新导出 host-sync 模块, 不重复实现 — 避免漂移.
"""

from __future__ import annotations

import importlib.util as _importlib_util
from pathlib import Path as _Path

_HOST_SYNC_PATH = _Path(__file__).with_name("zhixing-host-sync.py")
_spec = _importlib_util.spec_from_file_location(
    "_zhixing_host_sync_impl", _HOST_SYNC_PATH
)
assert _spec is not None and _spec.loader is not None
_impl = _importlib_util.module_from_spec(_spec)
_spec.loader.exec_module(_impl)

status = _impl.status
check = _impl.check
capture = _impl.capture
restore = _impl.restore

__all__ = ["capture", "check", "restore", "status"]
