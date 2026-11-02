"""BET-Y2Q4-T10-279 — bin/panorama/panorama-collect.py 的账本路径必须在调用时刻经 profile 缝解析。

钉住三件事：
1. **正向落点**：声明 ``OMOSTATION_STATE_ROOT`` 后，交给 digest 读者的账本路径真的落在那个
   state 根下，而不是当前检出。
2. **env 最高优先级**：``OMO_EVENT_LEDGER_DB`` 逐字采用。
3. **无 import 时冻结**：三个消费函数的 ``event_ledger`` 默认值必须是 ``None``；
   改回 ``= EVENT_LEDGER`` 这类模块级常量时本用例当场红（变异对照无需手工）。
"""

from __future__ import annotations

import importlib.util
import inspect
import pathlib
import types

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
COLLECTOR = REPO_ROOT / "bin" / "panorama" / "panorama-collect.py"
LEDGER_RELATIVE = pathlib.Path("runtime") / "omo" / "event-ledger.sqlite3"


class _Stop(Exception):
    """记录到路径后立即中断，避免跑进真实 ledger 读取。"""


@pytest.fixture(scope="module")
def collector():
    spec = importlib.util.spec_from_file_location("panorama_collect_t279", COLLECTOR)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def recorder(monkeypatch, collector):
    """把 digest 读者换成路径记录器；返回 (calls, module)。"""
    calls: list[pathlib.Path] = []

    def _fake_digest(path: pathlib.Path) -> str:
        calls.append(pathlib.Path(path))
        raise _Stop()

    monkeypatch.setattr(collector, "_event_ledger_logical_digest", _fake_digest)
    return calls, collector


def _call_and_capture(fn, **kwargs):
    try:
        fn(**kwargs)
    except _Stop:
        return
    pytest.fail(f"{fn.__name__} 未走到 digest 读者，无法取证路径")


def test_state_root_declared_lands_under_state_root(recorder, monkeypatch, tmp_path):
    """判据 1：正向落点 —— state 根声明后路径必须跟过去。"""
    calls, mod = recorder
    state = tmp_path / "state-root"
    monkeypatch.setenv("OMOSTATION_STATE_ROOT", str(state))
    monkeypatch.delenv("OMO_EVENT_LEDGER_DB", raising=False)
    _call_and_capture(mod.collect_personal_value_truth)
    assert calls == [state / LEDGER_RELATIVE]
    assert not str(calls[0]).startswith(str(REPO_ROOT)), "路径仍钉在检出根 ⇒ 写面没跟着 profile"


def test_explicit_env_ledger_wins(recorder, monkeypatch, tmp_path):
    """判据 2：OMO_EVENT_LEDGER_DB 是最高优先级，逐字采用。"""
    calls, mod = recorder
    explicit = tmp_path / "elsewhere" / "my-ledger.sqlite3"
    monkeypatch.setenv("OMOSTATION_STATE_ROOT", str(tmp_path / "state-root"))
    monkeypatch.setenv("OMO_EVENT_LEDGER_DB", str(explicit))
    _call_and_capture(mod.collect_personal_value_truth)
    assert calls == [explicit]


def test_undeclared_profile_keeps_checkout_ledger(recorder, monkeypatch):
    """回归保护：未声明 profile 时与历史布局逐字节一致（检出根下的同一相对路径）。"""
    calls, mod = recorder
    monkeypatch.delenv("OMOSTATION_STATE_ROOT", raising=False)
    monkeypatch.delenv("OMO_EVENT_LEDGER_DB", raising=False)
    _call_and_capture(mod.collect_personal_value_truth)
    assert calls == [REPO_ROOT / LEDGER_RELATIVE]


def test_explicit_argument_still_wins(recorder, monkeypatch, tmp_path):
    """显式传参（测试侧与调用方缝）不受影响。"""
    calls, mod = recorder
    given = tmp_path / "given.sqlite3"
    monkeypatch.setenv("OMOSTATION_STATE_ROOT", str(tmp_path / "state-root"))
    _call_and_capture(mod.collect_personal_value_truth, event_ledger=given)
    assert calls == [given]


@pytest.mark.parametrize(
    "fn_name",
    ["collect_personal_value_truth", "collect_projection_source_binding", "publish_projection_revision"],
)
def test_default_argument_is_not_frozen_at_definition(collector, fn_name):
    """判据 3：默认值必须是 None —— 写回模块级常量就是这个缺陷本身。"""
    fn = getattr(collector, fn_name)
    param = inspect.signature(fn).parameters["event_ledger"]
    assert param.default is None, f"{fn_name}.event_ledger 默认值被冻结成 {param.default!r}"


def test_module_has_no_import_time_ledger_constant(collector):
    """缺陷形状 1：模块级 EVENT_LEDGER 常量必须不存在（import 时求值 = 冻结在旧根）。"""
    assert not hasattr(collector, "EVENT_LEDGER")
    assert isinstance(getattr(collector, "event_ledger_path", None), types.FunctionType)
