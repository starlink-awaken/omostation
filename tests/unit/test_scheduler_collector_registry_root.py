"""scheduler 采集器的 registry 根必须与 A4 同源。

缺陷（BET-Y2Q4-T10-269，2026-10-26 实测）: A4 的 `collect_runtime()` 跑
`scheduler-compile.py --check` 时 `cwd=ROOT`（= `Path(panorama-collect.py).parents[2]`
= publisher 检出，每 180s 同步 origin/main）；而 cockpit 的 scheduler 采集器把根
硬编码成 `/Users/xiamingxing/Workspace`。同一个检查读两棵不同的 registry ——
A4 PASS 与 cockpit DEGRADED 可以同时为真，A9 于是为「主工作区陈旧」转 PARTIAL。

判据自证: 用例 4 把 `PANORAMA_CODE_ROOT` 指向一棵**合成的**检出，断言采集器实际
把工作目录切到它 —— 若 `collect()` 仍读硬编码根，该断言会红（否则「根解析生效」
可能只是检测器没接上）。
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
ASSET = ROOT / "bin/panorama/assets/host/scheduler_collector.py.asset"


def _load(monkeypatch, *, publisher: str | None):
    """Load the collector asset in isolation with the release import shims."""
    collectors = types.ModuleType("collectors")
    base = types.ModuleType("collectors.base")
    base.DataCollector = object
    base.CollectionError = type("CollectionError", (Exception,), {})
    registry = types.ModuleType("collectors.registry")
    registry.register = lambda *a, **k: (lambda cls: cls)
    monkeypatch.setitem(sys.modules, "collectors", collectors)
    monkeypatch.setitem(sys.modules, "collectors.base", base)
    monkeypatch.setitem(sys.modules, "collectors.registry", registry)

    if publisher is None:
        monkeypatch.delenv("PANORAMA_CODE_ROOT", raising=False)
    else:
        monkeypatch.setenv("PANORAMA_CODE_ROOT", publisher)
    monkeypatch.delenv("ZX_DASHBOARD_WORKSPACE_ROOT", raising=False)

    spec = importlib.util.spec_from_file_location(
        "scheduler_collector_under_test",
        ASSET,
        loader=importlib.machinery.SourceFileLoader("scheduler_collector_under_test", str(ASSET)),
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _stub_run_cmd(monkeypatch, module, seen: dict | None = None) -> None:
    def fake_run_cmd(argv, timeout=20, cwd=None):
        if seen is not None:
            seen["argv"] = list(argv)
            seen["cwd"] = cwd
        return '{"ok": true, "drift_count": 0, "orphan_count": 0, "command_exit_code": 0}'

    monkeypatch.setattr(module, "_run_cmd", fake_run_cmd)
    monkeypatch.setattr(module, "_git", lambda args, cwd: None)


def test_publisher_root_wins_when_it_carries_the_compiler(monkeypatch, tmp_path):
    (tmp_path / "bin").mkdir()
    (tmp_path / "bin/scheduler-compile.py").write_text("#!/usr/bin/env python3\n", encoding="utf-8")
    module = _load(monkeypatch, publisher=str(tmp_path))
    assert module.registry_root() == tmp_path.resolve()


def test_falls_back_to_workspace_root_without_the_env(monkeypatch, tmp_path):
    module = _load(monkeypatch, publisher=None)
    assert module.registry_root() == module.DEFAULT_WORKSPACE_ROOT


def test_falls_back_when_the_env_names_a_checkout_without_the_compiler(monkeypatch, tmp_path):
    empty = tmp_path / "not-a-checkout"
    empty.mkdir()
    module = _load(monkeypatch, publisher=str(empty))
    assert module.registry_root() == module.DEFAULT_WORKSPACE_ROOT


def test_collect_actually_runs_against_the_resolved_root(monkeypatch, tmp_path):
    """Self-proof: the resolved root must reach the subprocess, not just the resolver."""
    synthetic = tmp_path / "publisher"
    (synthetic / "bin/gac").mkdir(parents=True)
    (synthetic / "bin/scheduler-compile.py").write_text("#!/usr/bin/env python3\n", encoding="utf-8")
    module = _load(monkeypatch, publisher=str(synthetic))

    seen: dict = {}
    _stub_run_cmd(monkeypatch, module, seen)

    module.SchedulerCollector().collect()

    assert seen["cwd"] == synthetic.resolve(), (
        "采集器没有把工作目录切到解析出的根 —— 根解析形同虚设"
    )
    assert seen["argv"][0] == str(synthetic.resolve() / "bin/gac/managed-python")
    assert seen["argv"][-3:] == ["bin/scheduler-compile.py", "--check", "--json"]


def test_stale_flag_is_observe_only_and_reports_the_roots_own_origin_main(monkeypatch, tmp_path):
    module = _load(monkeypatch, publisher=str(tmp_path))
    _stub_run_cmd(monkeypatch, module)
    monkeypatch.setattr(module, "_git", lambda args, cwd: {
        ("rev-parse", "HEAD"): "a" * 40,
        ("rev-parse", "origin/main"): "b" * 40,
    }.get(tuple(args)))

    state = module.SchedulerCollector().collect()
    assert state["registry_root_stale"] is True
    assert state["registry_root_oid"] == "a" * 40
    # Observe-only: the flag must never reach the verdict.
    assert state["ok"] is True and state["state"] == "OBSERVED"
