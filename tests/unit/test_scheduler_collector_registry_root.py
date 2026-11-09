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
import json
import subprocess
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
    """Self-proof: the resolved root must reach the subprocess, not just the resolver.

    运行时 (managed-python) 来自工作区, 被检查的脚本来自解析出的 registry 根 ——
    两者都必须真的到达子进程, 否则「根解析生效」可能只是检测器没接上。
    """
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
    assert seen["argv"][0] == str(module.DEFAULT_WORKSPACE_ROOT / "bin/gac/managed-python"), (
        "运行时必须来自工作区 —— publisher 检出没有 .venv, managed-python 在那里解析不到解释器"
    )
    assert seen["argv"][-2] == str(synthetic.resolve() / "bin/scheduler-compile.py"), (
        "被检查的脚本必须来自解析出的 registry 根"
    )
    # 真实契约（哪些 flag 被被调用方接受）由
    # test_collector_flags_are_accepted_by_the_script_it_actually_invokes 跑真进程作证；
    # 这里只断言 argv 形状，避免把 stub 的返回值当契约。
    assert seen["argv"][-1:] == ["--check"]


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


def test_collector_flags_are_accepted_by_the_script_it_actually_invokes(monkeypatch, tmp_path):
    """反 stub-自证: 采集器传的 flag 必须被真实 scheduler-compile.py 接受。

    BET-Y2Q4-T10-343 —— 此前 `_stub_run_cmd` 返回一份手写 JSON，于是采集器传一个
    被调用方根本不认识的 `--json`（argparse rc=2）也能让全部用例保持绿色，A9 永久
    PARTIAL 无人发现。本用例把 stub 抓到的 argv 原样喂给仓内真脚本。
    """
    synthetic = tmp_path / "publisher"
    (synthetic / "bin/gac").mkdir(parents=True)
    (synthetic / "bin/scheduler-compile.py").write_text("#!/usr/bin/env python3\n", encoding="utf-8")
    real_script = ROOT / "bin/scheduler-compile.py"

    module = _load(monkeypatch, publisher=str(synthetic))
    seen: dict = {}
    _stub_run_cmd(monkeypatch, module, seen)
    module.SchedulerCollector().collect()

    script_arg = str(synthetic.resolve() / "bin/scheduler-compile.py")
    flags = seen["argv"][seen["argv"].index(script_arg) + 1 :]

    result = subprocess.run(
        [sys.executable, str(real_script), *flags],
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert result.returncode in (0, 1), (
        f"被调用方拒绝采集器传的 {flags}: rc={result.returncode} {result.stderr.strip()[:200]}"
    )
    payload = json.loads(result.stdout)
    assert isinstance(payload.get("ok"), bool)
    assert payload["ok"] == (result.returncode == 0)
