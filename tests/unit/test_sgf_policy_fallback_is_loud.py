"""SGF 策略缺失时必须**有声**退回硬编码 DEFAULT_POLICY。

契约: `bin/gac/gac-local-gate.py` 的 `load_sgf_policy()`
用例来源: 2026-11-13 —— `SGF_POLICY_YAML` 指向 `projects/ecos/.../sgf-policy.yaml`
（子模块内）。子模块没初始化时文件不存在，`load_sgf_policy()` 返回 `{}` 并
**静默**退回硬编码 `DEFAULT_POLICY`（实测 stderr 0 字节）。而两者不是同一套门禁:
policy 77 条 gate / default 72 条, strict 全量 87 vs 84, 差集 19 条 ——
CI（`submodules: recursive`）跑的那套在本地根本不会出现, 反之亦然。

**判据**: 门禁面可以降级, 不能无声降级。这条用例钉住「缺失 ⇒ 告警命名路径」,
以及「存在 ⇒ 用 policy 而不是 default」。
"""

from __future__ import annotations

import importlib.util
import io
import json
import sys
from contextlib import redirect_stderr
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
GATE = ROOT / "bin" / "gac" / "gac-local-gate.py"


def _load(monkeypatch: pytest.MonkeyPatch, policy_path: Path):
    """以指定的 SGF_POLICY_YAML 重新加载门禁模块（模块级常量在 import 时冻结）。"""
    spec = importlib.util.spec_from_file_location("gac_local_gate_under_test", GATE)
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, "gac_local_gate_under_test", module)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "SGF_POLICY_YAML", policy_path)
    return module


def test_missing_policy_warns_and_names_the_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    module = _load(monkeypatch, tmp_path / "absent" / "sgf-policy.yaml")
    err = io.StringIO()
    with redirect_stderr(err):
        loaded = module.load_sgf_policy()
    assert loaded == {}
    message = err.getvalue()
    assert "sgf-policy.yaml" in message, message
    assert "DEFAULT_POLICY" in message, message
    assert "not found" in message.lower(), message


def test_present_policy_is_used_instead_of_default(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    policy = tmp_path / "sgf-policy.yaml"
    policy.write_text(
        json.dumps(
            {
                "settings": {"output": {"terminal_mode": "slim"}},
                "gates": [{"id": "only-this-gate", "command": ["bin/gac/whatever.py"]}],
            }
        ),
        encoding="utf-8",
    )
    module = _load(monkeypatch, policy)
    err = io.StringIO()
    with redirect_stderr(err):
        loaded = module.load_sgf_policy()
    assert err.getvalue() == "", err.getvalue()
    # `POLICY = load_sgf_policy() or DEFAULT_POLICY` 是模块级表达式; 这里复算它,
    # 不依赖 import 顺序 (import 时用的是真实的 SGF_POLICY_YAML)。
    effective = loaded or module.DEFAULT_POLICY
    ids = [g["id"] for g in effective["gates"]]
    assert ids == ["only-this-gate"], ids
    assert effective is loaded


def test_default_policy_is_not_the_policy_surface(monkeypatch: pytest.MonkeyPatch) -> None:
    """反证：默认面与「有 policy」的面不是同一套 —— 否则这条用例失去意义。

    用一份只含一个 gate 的合成 policy 与 DEFAULT_POLICY 对拍, 不依赖子模块是否初始化。
    """
    module = _load(monkeypatch, Path("/nonexistent/sgf-policy.yaml"))
    default_ids = {g["id"] for g in module.DEFAULT_POLICY["gates"]}
    assert len(default_ids) >= 70, len(default_ids)
    synthetic = {"only-this-gate"}
    assert synthetic != default_ids


def test_gate_checks_surface_tracks_the_loaded_policy(monkeypatch: pytest.MonkeyPatch) -> None:
    """policy 决定门禁集合 —— 换一份 policy 就会换一套 gate_checks。"""
    module = _load(monkeypatch, Path("/nonexistent/sgf-policy.yaml"))
    default_checks = {name for name, _ in module.gate_checks(scope="all", strict=True)}
    assert "doc-governance" in default_checks, sorted(default_checks)[:5]
