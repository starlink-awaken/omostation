"""采集器失败路径必须带出子进程输出，不能只剩一句静态文案。

同族缺陷的第四、五份拷贝（#5246 修了 ruflo，#5251 修了 environment）：

- `workflow_collector.py.asset::_select_managed_python`：selector 非零退出时
  `raise CollectionError("workflow", "managed observer runtime probe failed")` ——
  静态文案，`receipt.stderr/stdout` 被丢弃。
- `collectors.orca.py.asset::collect`：orca 非零退出时落到
  `{"status": "UNAVAILABLE", "source": "none"}` —— 连 `error` 字段都没有；
  `except Exception: pass` 也把异常原因吞掉。

判据自证：把两处的原因拼接删掉，对应用例当场红。
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
ORCA_ASSET = ROOT / "bin/panorama/assets/host/collectors.orca.py.asset"
WORKFLOW_ASSET = ROOT / "bin/panorama/assets/host/workflow_collector.py.asset"


class _Proc:
    def __init__(self, returncode: int, stdout: str = "", stderr: str = ""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _shims(monkeypatch, collection_error=Exception):
    collectors = types.ModuleType("collectors")
    base = types.ModuleType("collectors.base")
    base.DataCollector = object
    base.CollectionError = collection_error
    registry = types.ModuleType("collectors.registry")
    registry.register = lambda *a, **k: (lambda cls: cls)
    monkeypatch.setitem(sys.modules, "collectors", collectors)
    monkeypatch.setitem(sys.modules, "collectors.base", base)
    monkeypatch.setitem(sys.modules, "collectors.registry", registry)


def _load(asset: Path, monkeypatch, name: str, extra=None):
    spec = importlib.util.spec_from_file_location(
        name, asset, loader=importlib.machinery.SourceFileLoader(name, str(asset)))
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_orca_failure_keeps_reason(monkeypatch):
    _shims(monkeypatch)
    module = _load(ORCA_ASSET, monkeypatch, "orca_collector_diag")
    monkeypatch.setattr(module.subprocess, "run", lambda *a, **k: _Proc(1, stderr="orca: daemon down"))
    monkeypatch.setattr(module, "_orca_binary", lambda: "/synthetic/orca")
    monkeypatch.setattr(module, "Path", lambda *a, **k: Path("/synthetic"))

    data = next(
        obj for obj in vars(module).values()
        if isinstance(obj, type) and obj.__name__ == "OrcaCollector"
    )().collect()

    assert data["status"] == "UNAVAILABLE"
    assert "orca: daemon down" in (data.get("error") or ""), "失败原因被丢弃"


def test_orca_exception_keeps_reason(monkeypatch):
    _shims(monkeypatch)
    module = _load(ORCA_ASSET, monkeypatch, "orca_collector_diag_exc")

    def boom(*a, **k):
        raise OSError("spawn failed")

    monkeypatch.setattr(module.subprocess, "run", boom)

    data = next(
        obj for obj in vars(module).values()
        if isinstance(obj, type) and obj.__name__ == "OrcaCollector"
    )().collect()

    assert data["status"] == "UNAVAILABLE"
    assert "spawn failed" in (data.get("error") or ""), "异常原因被 except: pass 吞掉"


def test_workflow_selector_failure_keeps_reason(monkeypatch, tmp_path):
    class _CollectionError(Exception):
        def __init__(self, source, reason, cause=None):
            self.source, self.reason, self.cause = source, reason, cause
            super().__init__(reason)

    _shims(monkeypatch, collection_error=_CollectionError)
    # workflow_collector 还 import omo.workflow —— 用 shim 顶掉
    omo = types.ModuleType("omo")
    workflow = types.ModuleType("omo.workflow")
    workflow.core = types.SimpleNamespace()
    workflow.diagnostics = types.SimpleNamespace()
    monkeypatch.setitem(sys.modules, "omo", omo)
    monkeypatch.setitem(sys.modules, "omo.workflow", workflow)

    module = _load(WORKFLOW_ASSET, monkeypatch, "workflow_collector_diag")
    monkeypatch.setattr(module.subprocess, "run",
                        lambda *a, **k: _Proc(2, stderr="selector: profile missing"))

    with pytest.raises(_CollectionError) as excinfo:
        module._select_managed_python(tmp_path)

    assert "selector: profile missing" in excinfo.value.reason, \
        "静态文案让板板上只剩一句 probe failed"
