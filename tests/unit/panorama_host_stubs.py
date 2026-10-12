"""live_server.py.asset 测试部署的宿主依赖脚手架 (#4574 capture 补全)。

live_server 在模块级 import collectors.personal_value / observatory_query /
runtime_paths。测试把 asset 部署到临时目录后:
- collectors(base/registry/personal_value)从仓内 asset 装成包, 目录插
  sys.path 后由 live_server 自行加载 —— 测的是真身逻辑, 零分叉;
- runtime_paths 无 asset 入仓, 以 stub 提供符号(测试不触及其行为);
- observatory_query 由测试手动加载(原脚手架逻辑, 不变)。
"""
from __future__ import annotations

import sys
import tempfile
import types
from pathlib import Path


def install_host_stubs(deployed: Path) -> None:
    deployed = str(deployed)
    if deployed not in sys.path:
        sys.path.insert(0, deployed)

    if "runtime_paths" in sys.modules:
        return
    runtime_paths = types.ModuleType("runtime_paths")
    runtime_paths.CODE_ROOT = Path("/tmp/stub-code-root")
    runtime_paths.STATE_ROOT = Path(tempfile.mkdtemp(prefix="stub-state-root-"))
    runtime_paths.ProjectionRevisionStore = type("ProjectionRevisionStore", (), {})
    runtime_paths.ProjectionStateError = type("ProjectionStateError", (Exception,), {})
    sys.modules["runtime_paths"] = runtime_paths
