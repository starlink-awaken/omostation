"""readiness 探针的「不可判定 ≠ 不可用」契约 (2026-09-30 系统性审计, 第 4/5 例).

**同一族缺陷, 两处**:

``workflow_entrypoint_check`` 与 ``managed_python_probe`` 原本都写成
``except (OSError, subprocess.TimeoutExpired) -> {"status": "degraded", "required": True}``,
即「进程起不来」与「30s 内没跑完」被当成同一件事。

后果是可复现的阻断链: 探针超时 -> ``checks[...]`` 带 required=True 且非 pass
-> ``degraded_checks`` 非空 -> readiness ``status="degraded"`` ->
claim 校验要求 ``ready`` 故拒绝 (``clone_identity_required``) -> integrate 阻塞。
2026-09-30 在 6+ 并发 agent 的机器上, 这两个探针均超过预算。

实测耗时 (2026-09-30, 修复后于真实工作区): ``workflow_entrypoint_check`` 在 clone 上
5.1s、在主工作区 18.5s —— 它不是 <1s 的廉价探针, 因为 ``managed-python`` 每次都要做一次
uv 解析。原 30s 预算在并发负载下只是勉强够用, 故默认值同时提到 60s。**注意: 代码注释
里曾写「正常耗时 < 1s」, 被这次实测证伪** —— 断言必须以实测为准 (P73 声明 ≠ 实测)。

**两条反向护栏** —— 防止后来的审计把真正的安全门一起放松:

* ``reinstall_path_dependencies`` 的 uv 可用性探针超时**仍然**返回失败。
  因为跳过 reinstall 就可能带着陈旧 wheel 发布 clone, 那是 E8 (2026-08-15 实证)
  的真实失效模式; 此处只拆异常让诊断信息不谎称「uv 探针失败」。
* ``call_claims_authority`` 超时**仍然** fail closed 抛 ``AUTHORITY_UNAVAILABLE``。
  写入准入的语义与 clone 健康度相反: 「我不知道高水位」必须是不许写,
  fail-closed 本身就是它的安全属性, 不是缺陷。
"""

from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, WORKSPACE / rel)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ac = _load("agent_clone", "bin/gac/agent-clone.py")
cl = _load("clone_lifecycle", "bin/gac/clone-lifecycle.py")

TIMEOUT = subprocess.TimeoutExpired(cmd=["probe"], timeout=1.0)


class _Raising:
    """替换 subprocess.run: 恒抛指定异常, 并记录是否真的带了 timeout 预算。"""

    def __init__(self, exc: BaseException) -> None:
        self.exc = exc
        self.saw_timeout: list[float | None] = []

    def __call__(self, *args, **kwargs):
        self.saw_timeout.append(kwargs.get("timeout"))
        raise self.exc


def _patched(mod, raiser: _Raising, monkeypatch):
    monkeypatch.setattr(mod.subprocess, "run", raiser)
    return raiser


# --------------------------------------------------------------------------
# 第 4 例: workflow_entrypoint_check
# --------------------------------------------------------------------------


def test_entrypoint_timeout_is_unverified_and_non_blocking(monkeypatch):
    _patched(ac, _Raising(TIMEOUT), monkeypatch)
    result = ac.workflow_entrypoint_check(str(WORKSPACE))
    assert result["status"] == "unverified", result
    assert result["required"] is False, "超时不得阻断 claim 准入"
    assert "timed out" in result["detail"]


def test_entrypoint_timeout_budget_is_configurable(monkeypatch):
    """预算与本文件其他超时一样可通过环境变量调整, 不再写死。"""
    monkeypatch.setenv("AGENT_CLONE_ENTRYPOINT_TIMEOUT", "97.5")
    reloaded = _load("agent_clone_env", "bin/gac/agent-clone.py")
    assert reloaded.ENTRYPOINT_TIMEOUT_SECONDS == 97.5

    raiser = _patched(reloaded, _Raising(TIMEOUT), monkeypatch)
    result = reloaded.workflow_entrypoint_check(str(WORKSPACE))
    assert raiser.saw_timeout == [97.5], f"调用点未使用可调预算: {raiser.saw_timeout}"
    assert result["status"] == "unverified"


def test_entrypoint_oserror_still_blocks(monkeypatch):
    """进程根本起不来是真故障 —— 必须保留 required。"""
    _patched(ac, _Raising(OSError("no such runner")), monkeypatch)
    result = ac.workflow_entrypoint_check(str(WORKSPACE))
    assert result["status"] == "degraded", result
    assert result["required"] is True


# --------------------------------------------------------------------------
# 第 5 例: managed_python_probe (同一块代码上方 40 行, 原样重复了同一错误)
# --------------------------------------------------------------------------


def test_managed_python_timeout_is_unverified_and_non_blocking(monkeypatch):
    _patched(ac, _Raising(TIMEOUT), monkeypatch)
    check, receipt = ac.managed_python_probe(str(WORKSPACE), "stdlib")
    assert check["status"] == "unverified", check
    assert check["required"] is False
    assert receipt is None
    assert "timed out" in check["detail"]


def test_managed_python_oserror_still_blocks(monkeypatch):
    _patched(ac, _Raising(OSError("no such runner")), monkeypatch)
    check, receipt = ac.managed_python_probe(str(WORKSPACE), "stdlib")
    assert check["status"] == "degraded", check
    assert check["required"] is True
    assert receipt is None


def test_managed_python_missing_runner_still_blocks(tmp_path, monkeypatch):
    """runner 不存在是真实故障, 走的是 os.path.isfile 分支, 不得被放松。"""
    check, receipt = ac.managed_python_probe(str(tmp_path), "stdlib")
    assert check["status"] == "degraded"
    assert check["required"] is True
    assert receipt is None


# --------------------------------------------------------------------------
# 反向护栏 1: uv 可用性探针超时仍失败 (E8 陈旧 wheel 防护)
# --------------------------------------------------------------------------


def test_uv_probe_timeout_still_reports_failure(monkeypatch):
    monkeypatch.setattr(ac, "extract_uv_path_dependencies", lambda _root: ["pkg-a"])
    _patched(ac, _Raising(TIMEOUT), monkeypatch)
    ok, msg = ac.reinstall_path_dependencies(str(WORKSPACE))
    assert ok is False, "无法确认 uv 可用时不得报告 reinstall 成功 (E8)"
    assert "timed out" in msg
    # 诊断信息必须说「超时」而不是谎称「uv 探针失败」
    assert "uv probe failed" not in msg


def test_uv_missing_still_reports_failure(monkeypatch):
    monkeypatch.setattr(ac, "extract_uv_path_dependencies", lambda _root: ["pkg-a"])
    _patched(ac, _Raising(FileNotFoundError("uv")), monkeypatch)
    ok, msg = ac.reinstall_path_dependencies(str(WORKSPACE))
    assert ok is False
    assert "not found" in msg


# --------------------------------------------------------------------------
# 反向护栏 2: 写入准入 (claims-authority) 必须 fail closed
# --------------------------------------------------------------------------


def test_claims_authority_timeout_fails_closed(monkeypatch):
    """写入准入语义与 clone 健康度相反: 不可判定 => 不许写。"""
    _patched(cl, _Raising(TIMEOUT), monkeypatch)
    try:
        cl.call_claims_authority("status", None)
    except RuntimeError as exc:
        assert str(exc) == "AUTHORITY_UNAVAILABLE", exc
    else:
        raise AssertionError("claims-authority 超时不得被放行")
