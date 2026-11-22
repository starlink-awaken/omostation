"""zhixing 驾驶舱的 strategy 探针必须读**规范检出**, 不是 `__file__` 派生的 code_root。

背景 (债条目 PANORAMA-A9-SOURCES-STALE-12D, 2026-11-22): 驾驶舱的刷新作业跑在
安装位 (`~/.local/opt/omostation`)，plist 的 `PYTHONPATH` 指向安装根的 `bin/lib`。
`repo_root.code_root()` 由 `__file__` 派生（ADR-0456 设计如此）⇒ 探针的读数面成了
安装位；而安装位**按构造没有** `.omo/_delivery/agent-workflows/`（该面 gitignored，
release clone 不带）⇒ 采集器读 runs 得 `empty_or_missing_directory` ⇒ `runs=0`
⇒ strategy 恒 PARTIAL，无论采集器本身修得多对。

采集器读的是**仓内数据面**（delivery 面 + `_truth/registry`），那是读平面的事，
不是运行面。
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import sys
import types
from pathlib import Path

ASSET = (
    Path(__file__).resolve().parents[1]
    / "bin" / "panorama" / "assets" / "host" / "refresh.py.asset"
)


def _load_asset():
    # 资产在 import 期就要 `import probe_utils`（同目录的宿主模块，测试环境没有）
    if "probe_utils" not in sys.modules:
        stub = types.ModuleType("probe_utils")
        stub.redact_secrets = lambda text: text
        sys.modules["probe_utils"] = stub
    # `.py.asset` 后缀不被 spec_from_file_location 识别 ⇒ 显式给 SourceFileLoader
    loader = importlib.machinery.SourceFileLoader("zhixing_refresh_probe", str(ASSET))
    spec = importlib.util.spec_from_loader("zhixing_refresh_probe", loader)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["zhixing_refresh_probe"] = mod
    spec.loader.exec_module(mod)
    return mod


class _Resolver:
    def __init__(self, install_root: Path, canonical: Path, state: Path) -> None:
        self._install_root = install_root
        self._canonical = canonical
        self._state = state

    def code_root(self) -> Path:
        return self._install_root

    def canonical_root(self) -> Path:
        return self._canonical

    def state_root(self) -> Path:
        return self._state


def test_probe_strategy_reads_canonical_checkout(monkeypatch, tmp_path):
    asset = _load_asset()
    captured: dict[str, object] = {}
    fake = types.ModuleType("strategy_sources")

    def _collect(workspace, state_root, library, app):
        captured["workspace"] = workspace
        captured["state_root"] = state_root
        return {"state": "OBSERVED", "source_states": [], "documents": [], "records": {}}

    fake.collect_strategy_sources = _collect
    monkeypatch.setitem(sys.modules, "strategy_sources", fake)

    install_root = tmp_path / "install-root"
    canonical = tmp_path / "Workspace"
    state = tmp_path / "state"
    asset.probe_strategy(root_resolver=_Resolver(install_root, canonical, state))

    assert captured["workspace"] == canonical, (
        "探针必须读规范检出 —— 读 `__file__` 派生的 code_root 会落到安装位, "
        "而安装位按构造没有 delivery 数据面"
    )
    assert captured["state_root"] == state


if __name__ == "__main__":
    import pytest

    sys.exit(pytest.main([__file__, "-q"]))
