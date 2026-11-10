"""ruflo 采集器失败时必须保留 verifier 的输出 —— 原因在 stdout，不在 stderr。

缺陷（2026-11-10 实测）：`ruflo-rf0-verify.py --json` 把报告（含失败项）打在
stdout，stderr 为空；而采集器原来写
`output = proc.stdout.strip() if ok else proc.stderr.strip()`
⇒ 失败时 `output` **恒为空串**，板板上只剩一句 FAIL 而无原因。实测 10:44:00 那次：
`{"status": "FAIL", "verifier": "…/ruflo-rf0-verify.py", "output": ""}`。

同仓的 `reference_cell_collector.py.asset` 早已改成 `(proc.stderr or proc.stdout)`
并写明理由（"非零退出时 verifier 的输出才是原因 —— 丢掉它，板板上只剩一句
verifier exited non-zero"）。本用例把同一口径钉在 ruflo 上。

判据自证：`test_failure_without_stdout_keeps_stderr` 覆盖反方向；把实现改回
`proc.stderr.strip()` 则 `test_failure_keeps_stdout_reason` 当场红。
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ASSET = ROOT / "bin/panorama/assets/host/ruflo_collector.py.asset"


class _Proc:
    def __init__(self, returncode: int, stdout: str = "", stderr: str = ""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _load(monkeypatch, proc: _Proc):
    """Load the collector asset in isolation with the release import shims."""
    collectors = types.ModuleType("collectors")
    base = types.ModuleType("collectors.base")
    base.DataCollector = object
    base.CollectionError = type("CollectionError", (Exception,), {})
    registry = types.ModuleType("collectors.registry")
    registry.register = lambda *a, **k: (lambda cls: cls)
    script_paths = types.ModuleType("collectors._script_paths")
    script_paths.resolve_script = lambda *a, **k: "/synthetic/bin/gac/ruflo-rf0-verify.py"
    monkeypatch.setitem(sys.modules, "collectors", collectors)
    monkeypatch.setitem(sys.modules, "collectors.base", base)
    monkeypatch.setitem(sys.modules, "collectors.registry", registry)
    monkeypatch.setitem(sys.modules, "collectors._script_paths", script_paths)

    spec = importlib.util.spec_from_file_location(
        "ruflo_collector_under_test",
        ASSET,
        loader=importlib.machinery.SourceFileLoader("ruflo_collector_under_test", str(ASSET)),
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    monkeypatch.setattr(module.subprocess, "run", lambda *a, **k: proc)
    return module


def _collector(module):
    return next(
        obj for obj in vars(module).values()
        if isinstance(obj, type) and obj.__name__ == "RufloCollector"
    )()


def test_failure_keeps_stdout_reason(monkeypatch):
    reason = '{"ok": false, "checks": {"daemon_stopped": false}, "schema": "ruflo-rf0-verify/v1"}'
    module = _load(monkeypatch, _Proc(returncode=1, stdout=reason, stderr=""))

    data = _collector(module).collect()

    assert data["status"] == "FAIL"
    assert "daemon_stopped" in data["output"], "失败原因被打 stdout 丢弃 —— 板板上只剩一句 FAIL"


def test_failure_without_stdout_keeps_stderr(monkeypatch):
    module = _load(monkeypatch, _Proc(returncode=1, stdout="", stderr="boom: timeout"))

    data = _collector(module).collect()

    assert data["status"] == "FAIL"
    assert "boom: timeout" in data["output"]


def test_success_still_reports_stdout(monkeypatch):
    module = _load(monkeypatch, _Proc(returncode=0, stdout='{"ok": true}', stderr=""))

    data = _collector(module).collect()

    assert data["status"] == "OK"
    assert '"ok": true' in data["output"]
