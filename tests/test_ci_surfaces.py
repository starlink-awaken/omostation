"""ADR-0379 E-1/E-2/E-3: CI 平面可观测性回归测试.

覆盖:
- check-ci-surfaces.py: unregistered-check / gate-parity / orphan-script /
  overlap / double-trigger 检测
- ci-check-runner.py: registry-driven 执行 (surface 选择 / orphan 跳过 / 失败聚合)

所有检测函数通过模块级路径常量 (CI_SURFACES / WORKFLOWS_DIR / SGF_POLICY)
工作, 测试用 monkeypatch 注入 tmp 路径隔离真实工作区.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def cs(monkeypatch, tmp_path):
    """check-ci-surfaces module with tmp-injected paths."""
    import sys

    bin_gac = str(ROOT / "bin" / "gac")
    if bin_gac not in sys.path:
        sys.path.insert(0, bin_gac)
    mod = _load(ROOT / "bin" / "gac" / "check-ci-surfaces.py", "check_ci_surfaces_test")
    monkeypatch.setattr(mod, "CI_SURFACES", tmp_path / "ci-surfaces.yaml")
    monkeypatch.setattr(mod, "WORKFLOWS_DIR", tmp_path / "workflows")
    monkeypatch.setattr(mod, "SGF_POLICY", tmp_path / "sgf-policy.yaml")
    (tmp_path / "workflows").mkdir()
    (tmp_path / "scripts").mkdir()
    return mod


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_live_registry_is_clean() -> None:
    """真实工作区: ci-surfaces SSOT 与接线一致, 0 error (warn 允许)."""
    mod = _load(ROOT / "bin" / "gac" / "check-ci-surfaces.py", "check_ci_surfaces_live")
    report = mod.check_ci_surfaces()
    assert report["ok"] is True, f"live CI plane has errors: {report['errors']}"
    assert report["surfaces"] >= 90, f"expected >=90 registered surfaces, got {report['surfaces']}"


def test_unregistered_check_detected(cs, tmp_path) -> None:
    """workflow 执行未登记 check 工具 → unregistered-check error."""
    _write(tmp_path / "ci-surfaces.yaml", "version: 1\nsurfaces: []\n")
    _write(
        tmp_path / "workflows" / "test.yml",
        "on: [push, pull_request]\n"
        "jobs:\n  t:\n    steps:\n      - run: python3 scripts/check-foo.py\n",
    )
    report = cs.check_ci_surfaces()
    assert any("unregistered-check" in e for e in report["errors"]), report["errors"]


def test_gate_parity_detected(cs, tmp_path) -> None:
    """sgf-policy gate 引用未登记工具 → gate-parity error."""
    _write(tmp_path / "ci-surfaces.yaml", "version: 1\nsurfaces: []\n")
    _write(
        tmp_path / "sgf-policy.yaml",
        "gates:\n  - id: foo\n    command: [\"bin/gac/check-unknown.py\"]\n",
    )
    report = cs.check_ci_surfaces()
    assert any("gate-parity" in e for e in report["errors"]), report["errors"]


def test_orphan_script_warns(cs, tmp_path) -> None:
    """磁盘上 check-*.py 未接线且未登记为 orphan → orphan-script warn."""
    _write(tmp_path / "ci-surfaces.yaml", "version: 1\nsurfaces: []\n")
    _write(tmp_path / "scripts" / "check-orphan-test.py", "print('ok')\n")
    report = cs.check_ci_surfaces()
    assert any("orphan-script" in w for w in report["warnings"]), report["warnings"]


def test_double_trigger_detected(cs, tmp_path) -> None:
    """on: [push, pull_request] 无 main 分支限制 → double-trigger error."""
    _write(tmp_path / "ci-surfaces.yaml", "version: 1\nsurfaces: []\n")
    _write(tmp_path / "workflows" / "dup.yml", "on: [push, pull_request]\n")
    report = cs.check_ci_surfaces()
    assert any("double-trigger" in e for e in report["errors"]), report["errors"]


def test_overlap_warns(cs, tmp_path) -> None:
    """同一 tool 在 2+ workflow → overlap warn."""
    _write(
        tmp_path / "ci-surfaces.yaml",
        "version: 1\nsurfaces:\n"
        "  - id: a\n    tool: scripts/check-foo.py\n    workflow: a.yml\n"
        "  - id: b\n    tool: scripts/check-foo.py\n    workflow: b.yml\n",
    )
    for name in ("a.yml", "b.yml"):
        _write(
            tmp_path / "workflows" / name,
            "on: push\njobs:\n  t:\n    steps:\n      - run: python3 scripts/check-foo.py\n",
        )
    report = cs.check_ci_surfaces()
    assert any("overlap" in w for w in report["warnings"]), report["warnings"]


def test_runner_selects_and_aggregates(monkeypatch, tmp_path) -> None:
    """runner: 只执行指定 workflow 的 surface, 失败聚合为 failures."""
    runner = _load(ROOT / "bin" / "gac" / "ci-check-runner.py", "ci_check_runner_test")
    ok_script = tmp_path / "ok-check.py"
    ok_script.write_text("print('ok')\n", encoding="utf-8")
    fail_script = tmp_path / "fail-check.py"
    fail_script.write_text("raise SystemExit(1)\n", encoding="utf-8")
    _write(
        tmp_path / "ci-surfaces.yaml",
        "version: 1\nsurfaces:\n"
        f"  - id: ok\n    tool: {ok_script}\n    workflow: gov.yml\n"
        f"  - id: bad\n    tool: {fail_script}\n    workflow: gov.yml\n"
        "  - id: other\n    tool: scripts/check-other.py\n    workflow: other.yml\n"
        f"  - id: orphan\n    tool: {ok_script}\n    workflow: gov.yml\n    status: orphan\n",
    )
    monkeypatch.setattr(runner, "CI_SURFACES", tmp_path / "ci-surfaces.yaml")
    report = runner.run_surfaces("gov.yml", cwd=tmp_path)
    assert report["selected"] == 2, f"orphan/other 不应被选中: {report}"
    assert report["failures"] == 1
    assert report["ok"] is False
    by_tool = {r["tool"]: r["ok"] for r in report["results"]}
    assert by_tool[str(ok_script)] is True
    assert by_tool[str(fail_script)] is False


def test_trigger_drift_detected(cs, tmp_path) -> None:
    """E-5: workflow 未登记 trigger/path_filter 差异 → trigger-drift warn."""
    _write(
        tmp_path / "ci-surfaces.yaml",
        "version: 1\nworkflow_triggers:\n  - workflow: a.yml\n    triggers: [push]\n    path_filtered: false\n",
    )
    _write(tmp_path / "workflows" / "a.yml", "on: [push, pull_request]\n")
    _write(tmp_path / "workflows" / "unregistered.yml", "on: push\n")
    report = cs.check_ci_surfaces()
    assert any("trigger-drift" in w for w in report["warnings"]), report["warnings"]


def test_trigger_drift_clean(cs, tmp_path) -> None:
    """E-5: 登记与实际情况一致 → 无 trigger-drift warn."""
    _write(
        tmp_path / "ci-surfaces.yaml",
        "version: 1\nworkflow_triggers:\n  - workflow: a.yml\n    triggers: [push, per_pr]\n    path_filtered: false\n",
    )
    _write(tmp_path / "workflows" / "a.yml", "on: [push, pull_request]\n")
    report = cs.check_ci_surfaces()
    assert not any("trigger-drift" in w for w in report["warnings"]), report["warnings"]


def test_trigger_paths_drift_detected(cs, tmp_path) -> None:
    """E-5 full: workflow paths 与实际登记不符 → trigger-drift warn."""
    _write(
        tmp_path / "ci-surfaces.yaml",
        "version: 1\nworkflow_triggers:\n  - workflow: a.yml\n    triggers: [push]\n    path_filtered: true\n    paths: [\".github/workflows/**\"]\n",
    )
    _write(
        tmp_path / "workflows" / "a.yml",
        "on:\n  push:\n    paths:\n      - 'docs/**'\n",
    )
    report = cs.check_ci_surfaces()
    assert any("paths 实际" in w for w in report["warnings"]), report["warnings"]


def test_trigger_paths_match_clean(cs, tmp_path) -> None:
    """E-5 full: paths 登记与实际一致 → 无 warn."""
    _write(
        tmp_path / "ci-surfaces.yaml",
        "version: 1\nworkflow_triggers:\n  - workflow: a.yml\n    triggers: [push]\n    path_filtered: true\n    paths: [\"docs/**\"]\n",
    )
    _write(
        tmp_path / "workflows" / "a.yml",
        "on:\n  push:\n    paths:\n      - 'docs/**'\n",
    )
    report = cs.check_ci_surfaces()
    assert not any("paths 实际" in w for w in report["warnings"]), report["warnings"]


def test_gate_effectiveness_module_loads():
    """ADR-0384 B1: gate-effectiveness 工具可导入并产出 JSON."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "gate_effectiveness_test", ROOT / "bin/gac/gate-effectiveness.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    # 已知数据集: 7 checks (governance-history.jsonl ≥ 500 events)
    stats = module.build_check_stats(
        [
            {
                "timestamp": "2026-08-01T00:00:00Z",
                "checks": [
                    {"category": "lint", "name": "ruff", "score": 90, "severity": "ok"},
                    {"category": "lint", "name": "ruff", "score": 70, "severity": "warn"},
                ],
            }
        ]
    )
    assert len(stats) == 1
    assert stats[0]["name"] == "ruff"
    assert stats[0]["fires"] == 1
    assert stats[0]["total"] == 2
    assert stats[0]["verdict"] in ("WEAK", "MODERATE", "ACTIVE", "NEW")


def test_ssot_usage_module_loads():
    """ADR-0385 B2: ssot-usage 模块可导入并产出结果."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "ssot_usage_test", ROOT / "bin/ssot/ssot-usage.py"
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    findings = mod.check_sots(max_age_days=36500)  # 100 年 → 0 stale
    assert len(findings) > 0, "应检测到至少 1 个 SSOT"
    assert all(not f["stale"] for f in findings)
