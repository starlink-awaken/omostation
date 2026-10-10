"""规则接线清单回归测试 — 锁住"报告型而非门禁"与其假阳边界.

背景 (2026-09-21): 17 项 debt item 用了契约外 gate_level (P0/P1/P2), 而契约、
omo `GATE_ORDER`、L0 注册表 `CR-DEBT-GATE-ENUM-01` 三者都齐 —— 唯独**没有执行器
引用它** (文档 §4 自陈"实现位置: 待补")。违规因此存在 3 个月。
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

TOOL = Path(__file__).resolve().parents[1] / "bin/gac/check-rule-wiring-coverage.py"


def _load():
    spec = importlib.util.spec_from_file_location("rule_cov", TOOL)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["rule_cov"] = mod
    spec.loader.exec_module(mod)
    return mod


def _run(*a: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(TOOL), *a],
                          capture_output=True, text=True, check=False)


# ── 报告型语义 (核心: 不得当门禁) ────────────────────────


def test_default_exit_is_zero_even_with_candidates():
    """有未接线候选时默认仍 exit 0 —— 假阳未知, 不能拦人。"""
    r = _run()
    assert r.returncode == 0, r.stdout + r.stderr
    assert "非门禁" in r.stdout


def test_strict_is_opt_in():
    r = _run("--strict", "--json")
    d = json.loads(r.stdout)
    has_cands = (d["sources"]["governance-checks"]["unreferenced"] > 0
                 or d["sources"]["L0-constraints(submodule)"]["unreferenced"] > 0)
    assert (r.returncode == 1) == has_cands


def test_caveat_is_emitted():
    """假阳边界必须出现在输出里, 否则使用者会把它当结论。"""
    r = _run()
    assert "假阳" in r.stdout or "别名" in r.stdout


# ── 语料取法 ────────────────────────────────────────────


def test_exec_corpus_excludes_registries(tmp_path, monkeypatch):
    """执行语料不得含注册表自身, 否则自引用让一切看起来都已接线。

    注: 断言的是**注册表文件不进语料**, 不是"注册表里的关键词不出现" —— 像
    `subtraction_quota` 这类键是工具**合法读取**的配置, 出现在脚本里是正常的。
    """
    mod = _load()
    fake_bin = tmp_path / "bin" / "gac"
    fake_bin.mkdir(parents=True)
    (fake_bin / "t.py").write_text("X = 'CR-FOO-01'\n", encoding="utf-8")
    reg = tmp_path / ".omo" / "_truth" / "registry"
    reg.mkdir(parents=True)
    (reg / "governance-checks.yaml").write_text("id: CR-FOO-01\n", encoding="utf-8")
    monkeypatch.setattr(mod, "_ROOT", tmp_path)
    monkeypatch.setattr(mod, "EXEC_MANIFEST", reg / "hook-manifest.yaml")
    blob = mod._exec_corpus()
    assert "CR-FOO-01" in blob, "脚本应进语料"
    # 注册表 yaml 不匹配任何 EXEC_CORPUS_GLOB, 故其内容不得出现在语料里
    assert "governance-checks" not in blob


def test_archive_and_registry_excluded():
    mod = _load()
    for pat in mod.EXEC_CORPUS_GLOBS:
        assert "_archive" not in pat


# ── 子模块不可用时的诚实降级 ────────────────────────────


def test_submodule_source_reports_unavailable_not_zero(tmp_path, monkeypatch):
    """子模块未初始化时必须报『跳过』, 不得报 0 条 → 避免误判全貌。"""
    mod = _load()
    monkeypatch.setattr(mod, "L0_SUBMODULE", tmp_path / "nope.yaml")
    inv = mod.inventory()
    l0 = inv["sources"]["L0-constraints(submodule)"]
    assert l0["available"] is False
    assert l0["declared"] == 0
    assert l0["note"], "必须给出说明, 而不是静默返回 0"


def test_rule_ids_parsed_from_declared_shape(tmp_path, monkeypatch):
    mod = _load()
    f = tmp_path / "rules.yaml"
    f.write_text(
        "gac:\n  rules:\n  - id: CR-FOO-01\n    check_type: x\n"
        "  - id: X2-C05\n  - id: not-a-rule-id\n", encoding="utf-8")
    ids = mod._rule_ids(f)
    assert "CR-FOO-01" in ids and "X2-C05" in ids
    assert "not-a-rule-id" not in ids


def test_missing_file_returns_empty(tmp_path):
    mod = _load()
    assert mod._rule_ids(tmp_path / "none.yaml") == []


# ── 真实仓库 ─────────────────────────────────────────────


def test_real_repo_has_declared_rules_and_exact_candidate_set():
    mod = _load()
    inv = mod.inventory()
    assert inv["sources"]["governance-checks"]["declared"] > 0
    assert inv["executed_ids_in_corpus"] > 0, "语料为空说明取法错了"
    # 精确候选集 (2026-10-10): CR-X4-HEALTH-SSOT 已接线 (alias → check_health_ssot
    # 真宿主, 见 registry-alias-map.yaml), 故 governance-checks 候选为**空集**。
    # 不等 "> 0" —— 旧断言钉死"必须永远存在未接线规则", 使诚实收尾无法发生;
    # 精确断言 = 恰好为空, 任何一侧漂移 (新候选出现 / 接线被移除) 都会红。
    # 注意: 本断言依赖 projects/*/src 子模块检出 (与 L0 候选断言同前提, CI 里递归检出)。
    got = set(inv["candidates_unwired"]["governance-checks"])
    assert got == set(), (
        f"governance-checks 候选漂移: got={sorted(got)} expected=[] "
        f"(接线 CR-X4-HEALTH-SSOT 后应为空; 新候选须逐条接线或更新本评审)"
    )
