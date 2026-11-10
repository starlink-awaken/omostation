"""CR-OMO-SURFACE-01 必须跳过 .gitignore 覆盖的本地产物。

缺陷背景 (2026-11-10 实测): `check_omo_surface_registration()` 用
`{p.name for p in (REPO/".omo").iterdir()}` 枚举顶层资产, 把 `.omo/.DS_Store`、
`.omo/_inbox/`、`.omo/reports/` 这些**已在 .gitignore 里**的本地产物也算成
「未登记的治理资产」⇒ 报 `[FAIL] CR-OMO-SURFACE-01`。

后果是判据与检出形态不兼容: **干净检出不报、本机报** (CI 绿而本地红),
且与 `bin/AGENTS.md` 的原则相悖 —— 「不在无效目录扫描里误杀未追踪运行目录」。

本文件钉两件事:
1. `_git_ignored()` 能识别 gitignore 覆盖的条目 (正反面);
2. 注册表覆盖全部**非忽略**顶层资产时判据通过, 且忽略项不出现在 missing 里。
"""

from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "bin" / "gac" / "check-l0-constraints.py"


@pytest.fixture()
def module():
    spec = importlib.util.spec_from_file_location("check_l0_constraints", SCRIPT)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _registered_top_level(registry: Path) -> set[str]:
    docs = list(yaml.safe_load_all(registry.read_text(encoding="utf-8")))
    data = next((d for d in docs if isinstance(d, dict) and "assets" in d), {})
    out: set[str] = set()
    for a in data.get("assets") or []:
        r = str((a or {}).get("ref", ""))
        if r.startswith(".omo/"):
            out.add(r[len(".omo/"):].split("/", 1)[0])
    return out


@pytest.fixture()
def omo_artifacts():
    """在真实 `.omo/` 下制造 gitignored 产物, 用完即删。

    `_git_ignored()` 走 `root.relative_to(REPO)`, 根必须在检出内, 故不能用
    pytest 的 tmp_path (在 /var/folders 下, 不在仓库里)。
    """
    omo = ROOT / ".omo"
    made = []
    for name, is_dir in (("reports", True), (".DS_Store", False)):
        p = omo / name
        if is_dir:
            p.mkdir(exist_ok=True)
        else:
            p.write_text("", encoding="utf-8")
        made.append(p)
    yield omo
    for p in made:
        try:
            p.rmdir() if p.is_dir() else p.unlink()
        except OSError:
            pass


def test_git_ignored_identifies_ignored_names(module, omo_artifacts: Path) -> None:
    """正反面: 真实 .gitignore 命中的要识别出来, 未命中的不得误豁免。"""
    names = {p.name for p in omo_artifacts.iterdir()}
    ignored = module._git_ignored(omo_artifacts, names)

    # .omo/reports 与 .omo/.DS_Store 在真实 .gitignore 里 (382/274 行)
    assert "reports" in ignored
    assert ".DS_Store" in ignored
    # 未被忽略的资产不得被误豁免 —— 否则判据会被整体架空
    assert "_truth" not in ignored


def test_git_ignored_returns_empty_on_probe_failure(module, omo_artifacts: Path, monkeypatch) -> None:
    """探测失败时退回空集 (不豁免), 保持判据偏严。"""
    def boom(*a, **k):
        raise RuntimeError("git unavailable")

    monkeypatch.setattr(module.subprocess, "run", boom)
    assert module._git_ignored(omo_artifacts, {"reports"}) == set()


def test_registration_check_tolerates_gitignored_artifacts(module, omo_artifacts: Path) -> None:
    """制造 gitignored 产物后, CR-OMO-SURFACE-01 仍须通过。

    这条直接打 `check_omo_surface_registration()` 本体 —— 上面两条只测
    `_git_ignored()` 这个零件, 把过滤那行删掉它们照样绿 (变异不红)。
    """
    ok, detail = module.check_omo_surface_registration()
    assert ok, detail


def test_real_registry_covers_every_non_ignored_top_level_asset(module) -> None:
    """真实仓库: 注册表覆盖 .omo 下全部非忽略顶层资产。

    这条是「判据没空转」的自证 —— 用真实注册表与真实 .omo 目录比对,
    并把忽略项排除后再断言, 避免忽略逻辑把判据整体架空。
    """
    registry = ROOT / ".omo" / "_truth" / "registry" / "omo-governance-surfaces.yaml"
    omo_root = ROOT / ".omo"
    if not registry.is_file() or not omo_root.is_dir():
        pytest.skip("registry/.omo 不在当前检出")

    registered = _registered_top_level(registry)
    actual = {p.name for p in omo_root.iterdir()}
    ignored = module._git_ignored(omo_root, actual)

    assert actual - ignored, "非忽略资产集为空 ⇒ 判据会被整体架空"
    missing = sorted((actual - ignored) - registered)
    assert missing == [], f"未登记且未被 gitignore 的顶层资产: {missing}"
