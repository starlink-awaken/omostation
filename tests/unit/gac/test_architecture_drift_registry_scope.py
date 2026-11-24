"""`architecture-drift` 的登记判定必须扫**全部分类目录**，不是只扫 `governance/`。

缺陷（2026-11-24 实测）：`check_registry_drift()` 用
`registry_dir / "governance" / f"{f.stem}.yaml"` 判断「脚本是否已登记」—— 把分类
目录写死成 `governance`。而登记面按 category 分子目录（`governance/`、`state/`、
`knowledge/`、`workflow/`…），于是登记在别的分类下的脚本全被报成「未注册」：

    脚本未注册: check-project-health-freshness.py   (实际在 state/)
    脚本未注册: check-adr-iteration-rate.py         (实际在 knowledge/)
    脚本未注册: check-silent-workflows.py           (实际在 workflow/)
    脚本未注册: health-trend-predictor.py           (实际在 state/)

四条全是误报，且 `--check` 会把它们当警告打出来 —— 警告一旦恒有，读者就学会忽略
整份报告（与 `check-readme-hardcoded` 那次「误报训练读者」同族）。

判据来源必须是登记面本身（同 AGENTS.md §7「检测器的分类规则要与标记清单同源」），
因此改为读全部条目里的 `id` 字段。
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "bin" / "gac" / "architecture-drift.py"


@pytest.fixture()
def module():
    spec = importlib.util.spec_from_file_location("architecture_drift_reg_test", SCRIPT)
    assert spec and spec.loader
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    return m


def _seed(tmp_path: Path, category: str, sid: str) -> None:
    d = tmp_path / "scripts" / category
    d.mkdir(parents=True)
    (d / f"{Path(sid).stem}.yaml").write_text(f"id: {sid}\n", encoding="utf-8")


def test_registered_ids_covers_every_category(tmp_path: Path, module) -> None:
    """三个不同分类下的登记都要被认出来 —— 旧实现只认 governance。"""
    for category, sid in (
        ("governance", "bin/gac/a.py"),
        ("state", "bin/gac/b.py"),
        ("knowledge", "bin/gac/c.py"),
        ("workflow", "bin/gac/d.py"),
    ):
        _seed(tmp_path, category, sid)

    assert module.registered_ids(tmp_path / "scripts") == {
        "bin/gac/a.py",
        "bin/gac/b.py",
        "bin/gac/c.py",
        "bin/gac/d.py",
    }


def test_registered_ids_is_empty_on_absent_registry(tmp_path: Path, module) -> None:
    """反证：空登记面就是空集合，判据不得把「没扫到」当成「都登记了」。"""
    assert module.registered_ids(tmp_path / "nothing-here") == set()


def test_registered_ids_tolerates_broken_entry(tmp_path: Path, module) -> None:
    """单条坏 YAML 不该让整次扫描崩掉。"""
    _seed(tmp_path, "governance", "bin/gac/good.py")
    (tmp_path / "scripts" / "governance" / "broken.yaml").write_text(
        "id: [unclosed\n", encoding="utf-8"
    )
    assert module.registered_ids(tmp_path / "scripts") == {"bin/gac/good.py"}


def test_check_registry_drift_does_not_flag_scripts_registered_in_other_categories(
    tmp_path: Path, module, monkeypatch
) -> None:
    """端到端：登记在 `state/`（非 governance）下的脚本不得被报成「未注册」。

    这正是当初误报的形状 —— 只钉 `registered_ids()` 是抓不住的（它本身没错，
    错的是调用方按分类目录猜），所以判据必须落在 `check_registry_drift()` 上。
    """
    reg = tmp_path / "bin" / "_registry" / "scripts" / "state"
    reg.mkdir(parents=True)
    (reg / "elsewhere.yaml").write_text("id: bin/gac/elsewhere.py\n", encoding="utf-8")
    gac_dir = tmp_path / "bin" / "gac"
    gac_dir.mkdir(parents=True)
    (gac_dir / "elsewhere.py").write_text("# live script\n", encoding="utf-8")

    monkeypatch.setattr(module, "REPO", tmp_path)
    assert module.check_registry_drift() == [], "登记在 state/ 下却被报成未注册"


def test_check_registry_drift_still_flags_genuinely_unregistered_script(
    tmp_path: Path, module, monkeypatch
) -> None:
    """反证：真的没登记的仍要报 —— 否则上一条只是把判据整体关掉。"""
    (tmp_path / "bin" / "_registry" / "scripts").mkdir(parents=True)
    gac_dir = tmp_path / "bin" / "gac"
    gac_dir.mkdir(parents=True)
    (gac_dir / "never_registered.py").write_text("# x\n", encoding="utf-8")

    monkeypatch.setattr(module, "REPO", tmp_path)
    assert module.check_registry_drift() == ["脚本未注册: never_registered.py"]


def test_the_four_previously_misreported_scripts_are_registered(module) -> None:
    """真实登记面上，当初被误报的四条必须都在。"""
    ids = module.registered_ids(module.REPO / "bin" / "_registry" / "scripts")
    for name in (
        "check-project-health-freshness.py",
        "check-adr-iteration-rate.py",
        "check-silent-workflows.py",
        "health-trend-predictor.py",
    ):
        assert f"bin/gac/{name}" in ids, f"{name} 仍被判成未登记"
