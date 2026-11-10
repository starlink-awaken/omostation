"""environment_evidence 采集器失败时必须带出原因，不能只剩一句 FAIL。

缺陷（2026-11-10 复核 #5246 时同族发现）：`collectors.environment.py.asset` 的失败分支
原本把子进程输出整个丢掉 —— `live = json.loads(proc.stdout) if ok else {}`，
返回体里也没有 error 字段。于是 meta-doctor 非零退出时，板板上只有一句
`{"status": "FAIL", "error": null}`，看不出是超时、缺文件还是校验失败。

同仓的 `ruflo_collector.py.asset`（#5246）与 `reference_cell_collector.py.asset`
早已是 `(proc.stderr or proc.stdout)` 口径并写明理由。本用例把同一口径钉在
environment 采集器上。

判据自证：把失败分支的 `reason` 赋值删掉，对应用例当场红。
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ASSET = ROOT / "bin/panorama/assets/host/collectors.environment.py.asset"


class _Proc:
    def __init__(self, returncode: int, stdout: str = "", stderr: str = ""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _load(monkeypatch, proc: _Proc):
    collectors = types.ModuleType("collectors")
    base = types.ModuleType("collectors.base")
    base.DataCollector = object
    base.CollectionError = type("CollectionError", (Exception,), {})
    registry = types.ModuleType("collectors.registry")
    registry.register = lambda *a, **k: (lambda cls: cls)
    monkeypatch.setitem(sys.modules, "collectors", collectors)
    monkeypatch.setitem(sys.modules, "collectors.base", base)
    monkeypatch.setitem(sys.modules, "collectors.registry", registry)

    spec = importlib.util.spec_from_file_location(
        "environment_collector_under_test",
        ASSET,
        loader=importlib.machinery.SourceFileLoader(
            "environment_collector_under_test", str(ASSET)),
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    monkeypatch.setattr(module.subprocess, "run", lambda *a, **k: proc)
    return module


def _collector(module):
    return next(
        obj for obj in vars(module).values()
        if isinstance(obj, type) and obj.__name__ == "EnvironmentEvidenceCollector"
    )()


def test_failure_keeps_stderr_reason(monkeypatch):
    module = _load(monkeypatch, _Proc(returncode=1, stdout="", stderr="meta-doctor: boom"))

    data = _collector(module).collect()

    assert data["status"] == "FAIL"
    assert data.get("error") == "meta-doctor: boom", "失败原因被丢弃 —— 板板上只剩一句 FAIL"


def test_failure_falls_back_to_stdout(monkeypatch):
    module = _load(monkeypatch, _Proc(returncode=1, stdout="parse error detail", stderr=""))

    data = _collector(module).collect()

    assert "parse error detail" in (data.get("error") or "")


def test_success_has_no_error(monkeypatch):
    module = _load(monkeypatch, _Proc(returncode=0, stdout='{"refs": []}', stderr=""))

    data = _collector(module).collect()

    assert data["status"] == "OK"
    assert data.get("error") is None
