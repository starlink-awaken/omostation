"""`gac-executor` 的「未注册/缺失」判定必须把**未检出的子模块**单独归类。

缺陷（2026-11-24 实测）：`check_executor_presence()` 只看候选文件在不在，于是一个
executor 的候选全在 `projects/<sub>/…` 时，**任何干净检出**都会把它报成缺失 ——
实测 `omo_audit` / `mof_audit` / `mcp_tool` 三条，`missing=3 / 受影响规则=35`，
而 `gac-healthcheck` 又把这条当成 ❌ 打出来。补齐子模块后同一调用是 `missing: []`。

这与 `GATE-CLEAN-CHECKOUT-NOISE` 同族：**输入没备齐**被当成 **finding**，
而恒假的警告会训练读者忽略整份报告。判据上必须分开：真缺失 vs 读数不可用。
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "bin" / "gac" / "gac-executor.py"


def _load(tmp_path: Path, monkeypatch):
    spec = importlib.util.spec_from_file_location("gac_executor_unchecked_test", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "WORKSPACE", tmp_path)
    return module


def test_candidate_inside_absent_submodule_is_not_missing(tmp_path: Path, monkeypatch) -> None:
    """候选全在未检出的子模块里 ⇒ 读数不可用，不是缺失。"""
    module = _load(tmp_path, monkeypatch)
    (tmp_path / "projects" / "omo").mkdir(parents=True)  # 未 init 的检出形状：空目录、无 .git

    exists, detail, unchecked = module.check_executor_presence("omo_audit")
    assert exists is False
    assert unchecked is True, detail
    assert "未检出" in detail


def test_genuinely_absent_candidate_is_still_missing(tmp_path: Path, monkeypatch) -> None:
    """反证：候选在仓内且真不存在时，仍须判缺失 —— 否则上一条只是把判据关掉。"""
    module = _load(tmp_path, monkeypatch)

    exists, detail, unchecked = module.check_executor_presence("ci_gate")  # .github/workflows/gac-gate.yml
    assert exists is False
    assert unchecked is False
    assert "候选都不存在" in detail


def test_run_check_separates_the_two_in_report(tmp_path: Path, monkeypatch, capsys) -> None:
    """端到端：合成登记面跑一遍，missing 为空而 not_checked 点名。"""
    module = _load(tmp_path, monkeypatch)
    (tmp_path / "projects" / "omo").mkdir(parents=True)
    (tmp_path / "projects" / "ecos").mkdir(parents=True)
    registry = tmp_path / ".omo/_truth/registry/governance-checks.yaml"
    registry.parent.mkdir(parents=True)
    registry.write_text(
        "gac:\n"
        "  rules:\n"
        "    - id: R1\n      executor: [omo_audit]\n"
        "    - id: R2\n      executor: [ci_gate]\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(module, "REGISTRY", registry)

    assert module.run_check(as_json=True) == 1  # R2 真缺失 ⇒ 退出码仍是 1

    payload = json.loads(capsys.readouterr().out)
    assert payload["missing_executors"] == ["ci_gate"]
    assert payload["executors_not_checked"] == ["omo_audit"]
    assert payload["rules_with_missing_executor"] == 1, "未判定项不该算进受影响规则"


def test_all_present_checkout_reports_neither_list(tmp_path: Path, monkeypatch) -> None:
    """子模块齐备时两个列表都该空 —— 别把『修好了』读成『还在报』。"""
    module = _load(tmp_path, monkeypatch)
    for rel in ("projects/omo/src/omo/cli.py", "projects/ecos/src/ecos/ssot/tools/mof-audit.py"):
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("# present\n", encoding="utf-8")

    assert module.check_executor_presence("omo_audit")[2] is False
    assert module.check_executor_presence("mof_audit")[2] is False
