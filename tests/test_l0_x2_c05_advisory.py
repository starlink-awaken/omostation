"""X2-C05 降级为非阻塞的回归守卫 (2026-11-09 governance-team 拆墙决策)。

背景: `check_x2_c05` 原是 required `gac-gate` 上的墙钟硬失败项 (age > 14 ⇒ return False
⇒ `check-l0-constraints.py` exit 1 ⇒ 每个 PR 都红)。2026-08-22 引入当天就得先盖一次戳
才通过, 此后四次到期都只靠再盖章续命 —— 14 天周期 << 人工深度复核的实际间隔。

本文件钉住降级后的行为, 三条判据两两不共享失效模式:
  1. 陈旧时不阻塞: `check_x2_c05()` 返回 True (旧实现返回 False) —— 这是**核心断言**,
     装回旧实现即红。
  2. 陈旧时仍然**可见**: 返回的 detail 里带 WARNING 与超期天数, 不是一句"跳过"。
  3. 新鲜时不误报: 未超期返回 fresh, 不含 WARNING。

用合成 fixture (临时 YAML), 不读真实注册表 —— 真实注册表哪天被盖戳都不影响本用例。
"""

from __future__ import annotations

import importlib.util
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

_MODULE_PATH = Path(__file__).resolve().parents[1] / "bin" / "gac" / "check-l0-constraints.py"


@pytest.fixture()
def l0_module(tmp_path, monkeypatch):
    """加载 check-l0-constraints 并把 OMO_SURFACES 指到合成 fixture。"""
    spec = importlib.util.spec_from_file_location("check_l0_constraints", _MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    surfaces = tmp_path / "omo-governance-surfaces.yaml"
    monkeypatch.setattr(module, "OMO_SURFACES", surfaces)
    return module, surfaces


def _write_surfaces(path: Path, last_reviewed: str) -> None:
    path.write_text(
        "---\n"
        "status: active\n"
        "lifecycle: ssot\n"
        "owner: governance-team\n"
        f"last-reviewed: {last_reviewed}\n"
        "---\n",
        encoding="utf-8",
    )


def test_stale_surfaces_does_not_block_but_warns(l0_module):
    """核心断言: 超期 ⇒ 返回 True (不阻塞), 且 detail 带 WARNING 与天数。"""
    module, surfaces = l0_module
    stale = (datetime.now(UTC).date() - timedelta(days=20)).isoformat()
    _write_surfaces(surfaces, stale)

    passed, detail = module.check_x2_c05()

    assert passed is True, "X2-C05 已降级为 advisory, 超期不得再返回 False (旧实现会)"
    assert "WARNING" in detail
    assert "20d" in detail


def test_fresh_surfaces_is_silent(l0_module):
    module, surfaces = l0_module
    fresh = (datetime.now(UTC).date() - timedelta(days=3)).isoformat()
    _write_surfaces(surfaces, fresh)

    passed, detail = module.check_x2_c05()

    assert passed is True
    assert "WARNING" not in detail
    assert "fresh" in detail


def test_missing_last_reviewed_is_advisory_not_blocking(l0_module):
    module, surfaces = l0_module
    surfaces.write_text("---\nstatus: active\nlifecycle: ssot\n---\n", encoding="utf-8")

    passed, detail = module.check_x2_c05()

    assert passed is True
    assert "advisory" in detail


def test_boundary_at_exactly_14_days_still_passes(l0_module):
    """阈值口径与降级前一致 (age > 14 才告警), 避免降级顺手改了判定边界。"""
    module, surfaces = l0_module
    boundary = (datetime.now(UTC).date() - timedelta(days=14)).isoformat()
    _write_surfaces(surfaces, boundary)

    passed, detail = module.check_x2_c05()

    assert passed is True
    assert "WARNING" not in detail


def test_main_still_exits_zero_when_only_x2_c05_is_stale(l0_module):
    """端到端: 即使 X2-C05 超期, `main()` 也不应因它 exit 1。

    把其余 15 项检查的结果强制为通过 (它们依赖子模块检出, 与本用例结论无关),
    只留真实的 X2-C05 —— 断言的是「X2-C05 不参与 all_pass 判定」。
    """
    module, surfaces = l0_module
    stale = (datetime.now(UTC).date() - timedelta(days=99)).isoformat()
    _write_surfaces(surfaces, stale)

    all_pass = True
    for cid, fn in [
        ("X1-C01", module.check_x1_c01),
        ("X1-C03", module.check_x1_c03),
        ("CR-MCP-LAZY-01", module.check_cr_mcp_lazy_01),
        ("CS-10", module.check_cs10),
        ("X2-C01", module.check_x2_c01),
        ("X2-C03", module.check_x2_c03),
        ("X2-C04", module.check_x2_c04),
        ("X2-C05", module.check_x2_c05),
        ("X3-C01", module.check_x3_c01),
        ("X3-C02", module.check_x3_c02),
        ("X3-C03", module.check_x3_c03),
        ("X4-C01", module.check_x4_c01),
        ("CR-OMO-SURFACE-01", module.check_omo_surface_registration),
        ("CR-OMO-SURFACE-02", module.check_omo_surface_02),
        ("CR-C2G-V3-01", module.check_c2g_v3_01),
    ]:
        if cid == "X2-C05":
            passed, _ = fn()
        else:
            passed = True
        if not passed:
            all_pass = False

    assert all_pass, "X2-C05 超期时端到端仍应全通过 (它已降级为 advisory)"
