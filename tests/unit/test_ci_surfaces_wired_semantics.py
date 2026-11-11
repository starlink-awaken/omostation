"""`wired_tools` 的口径：**已登记面**里有多少有执行面。

缺陷（2026-11-11 自证）：旧口径是 `len(wiring)` —— `wiring` 来自
`_discover_wiring()`（workflow 文本 + sgf-policy），于是这个「wired」数字
**含未登记的工具**（实测 147 里有 13 个不在 ci-surfaces 里）、又**漏掉只经
`gac-local-gate.py` 执行的工具**（`local_gate_tools` 有 86 个，其中 70 个已登记）。

同一个数字因此有三种读法：len(wiring)=147、registered∩wired=134、
并上本地门禁=138 —— 而它跟 `surfaces`（登记面总数）并排打印，读者会当成
「157 个登记面里有 147 个接线」，实际不是。

判据：`wired_tools = |(wiring ∪ local_gate_tools) ∩ registered_tools|`，
输出带分母 `wired=X/Y`。
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "bin" / "gac" / "check-ci-surfaces.py"


def _load():
    spec = importlib.util.spec_from_file_location("ci_surfaces_wired_probe", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MODULE = _load()


def _registered_tools() -> list[str]:
    reg = yaml.safe_load((ROOT / ".omo" / "_truth" / "registry" / "ci-surfaces.yaml").read_text(encoding="utf-8"))
    return [s["tool"] for s in reg["surfaces"] if s.get("tool")]


def test_wired_counts_registered_tools_with_execution_surface(monkeypatch) -> None:
    """一个只经 workflow、一个只经 gac-local-gate 的已登记工具都要算 wired。"""
    a, b = _registered_tools()[0], _registered_tools()[1]
    monkeypatch.setattr(MODULE, "_discover_wiring", lambda: {a: {"workflows": ["w.yml"], "gate": False}})
    monkeypatch.setattr(MODULE, "_local_gate_tools", lambda: {b})
    rep = MODULE.check_ci_surfaces()
    assert rep["wired_tools"] == 2, f"wired={rep['wired_tools']} (期望 2)"


def test_unregistered_wired_tools_do_not_count(monkeypatch) -> None:
    """反例保护: 未登记的工具不在 ci-surfaces 里, 不应计入 wired。"""
    ghost = "bin/not-registered-xyz.py"
    assert ghost not in _registered_tools()
    monkeypatch.setattr(MODULE, "_discover_wiring", lambda: {ghost: {"workflows": ["w.yml"], "gate": False}})
    monkeypatch.setattr(MODULE, "_local_gate_tools", lambda: set())
    rep = MODULE.check_ci_surfaces()
    assert rep["wired_tools"] == 0, f"未登记工具被计入 wired: {rep['wired_tools']}"


def test_wired_never_exceeds_registered_surfaces(monkeypatch) -> None:
    """即使接线表比登记面大得多, wired 也必须等于登记面数 (口径是子集, 不是全集)。"""
    registered = _registered_tools()
    wiring = {t: {"workflows": ["w.yml"], "gate": False} for t in registered}
    wiring.update({f"bin/ghost-{i}.py": {"workflows": ["w.yml"], "gate": False} for i in range(50)})
    monkeypatch.setattr(MODULE, "_discover_wiring", lambda: wiring)
    monkeypatch.setattr(MODULE, "_local_gate_tools", lambda: set())
    rep = MODULE.check_ci_surfaces()
    assert rep["wired_tools"] == len(registered), f"wired={rep['wired_tools']} 登记面={len(registered)}"
    assert rep["wired_tools"] <= rep["surfaces"]
