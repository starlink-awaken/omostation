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
    monkeypatch.setattr(mod, "WORKSPACE", tmp_path)
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


def test_script_registry_validation_is_bound_to_gac_gate() -> None:
    import yaml

    payload = yaml.safe_load(
        (ROOT / ".omo/_truth/registry/ci-surfaces.yaml").read_text(encoding="utf-8")
    )
    surface = next(
        item
        for item in payload["surfaces"]
        if item["id"] == "bin-ssot-script-registry-py"
    )

    assert surface["tool"] == "bin/ssot/script-registry.py"
    assert surface["workflow"] == "gac-gate.yml"
    assert surface["gate"] is True
    assert surface["triggers"] == ["manual", "per_pr", "push"]
    assert not ({"job", "step", "job_id", "step_id", "required"} & set(surface))

    workflow = yaml.safe_load(
        (ROOT / ".github/workflows/gac-gate.yml").read_text(encoding="utf-8")
    )
    strict = next(
        item
        for item in workflow["jobs"]["gac-gate"]["steps"]
        if item.get("name") == "gac-local-gate (strict)"
    )
    assert strict["run"] == "python3 bin/gac/gac-local-gate.py --strict"

    gate = _load(ROOT / "bin/gac/gac-local-gate.py", "gac_local_gate_ci_binding")
    commands = {item["id"]: item["command"] for item in gate.GATES_LIST}
    assert commands["script-registry-validate"] == [
        "python3",
        "bin/ssot/script-registry.py",
        "validate",
    ]


def test_meta_doctor_registry_binds_refs_only(monkeypatch) -> None:
    """registry-driven governance CI must preserve the refs-only contract."""
    runner = _load(ROOT / "bin" / "gac" / "ci-check-runner.py", "ci_check_runner_meta_doctor")
    calls = []

    class Result:
        returncode = 0
        stdout = ""
        stderr = ""

    def fake_run(cmd, **kwargs):
        calls.append(list(cmd))
        return Result()

    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    report = runner.run_surfaces("governance-check.yml", cwd=ROOT)

    assert report["ok"] is True
    meta_doctor_calls = [
        cmd for cmd in calls if len(cmd) >= 2 and cmd[1] == "bin/gac/meta-doctor.py"
    ]
    assert meta_doctor_calls == [
        [runner.sys.executable, "bin/gac/meta-doctor.py", "--refs-only"]
    ]


def test_removed_mutators_are_not_bound_to_gac_gate() -> None:
    import yaml

    payload = yaml.safe_load(
        (ROOT / ".omo/_truth/registry/ci-surfaces.yaml").read_text(encoding="utf-8")
    )
    surfaces = {item["id"]: item for item in payload["surfaces"]}

    exporter = surfaces["bin-gac-gac-export-agents-py"]
    assert exporter["workflow"] == "(none)"
    assert exporter["triggers"] == []

    sync = surfaces["bin-ssot-sync-submodule-pointers-sh"]
    assert sync["workflow"] == "(none)"  # workspace.yml 已删除 (与 gac-gate 可达性检查重复)
    assert sync["triggers"] == []
    assert "also_in" not in sync


def test_unregistered_check_detected(cs, tmp_path) -> None:
    """workflow 执行未登记 check 工具 → unregistered-check error."""
    _write(tmp_path / "ci-surfaces.yaml", "version: 1\nsurfaces: []\n")
    _write(
        tmp_path / "workflows" / "test.yml",
        "on: [push, pull_request]\njobs:\n  t:\n    steps:\n      - run: python3 scripts/check-foo.py\n",
    )
    report = cs.check_ci_surfaces()
    assert any("unregistered-check" in e for e in report["errors"]), report["errors"]


def test_gate_parity_detected(cs, tmp_path) -> None:
    """sgf-policy gate 引用未登记工具 → gate-parity error."""
    _write(tmp_path / "ci-surfaces.yaml", "version: 1\nsurfaces: []\n")
    _write(
        tmp_path / "sgf-policy.yaml",
        'gates:\n  - id: foo\n    command: ["bin/gac/check-unknown.py"]\n',
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
        'version: 1\nworkflow_triggers:\n  - workflow: a.yml\n    triggers: [push]\n    path_filtered: true\n    paths: [".github/workflows/**"]\n',
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
        'version: 1\nworkflow_triggers:\n  - workflow: a.yml\n    triggers: [push]\n    path_filtered: true\n    paths: ["docs/**"]\n',
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

    spec = importlib.util.spec_from_file_location("gate_effectiveness_test", ROOT / "bin/_archive/gate-effectiveness.py")
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
                    {
                        "category": "lint",
                        "name": "ruff",
                        "score": 70,
                        "severity": "warn",
                    },
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

    spec = importlib.util.spec_from_file_location("ssot_usage_test", ROOT / "bin/ssot/ssot-usage.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    findings = mod.check_sots(max_age_days=36500)  # 100 年 → 0 stale
    assert len(findings) > 0, "应检测到至少 1 个 SSOT"
    assert all(not f["stale"] for f in findings)


def test_missing_tool_detected(cs, tmp_path) -> None:
    """登记的工具文件不存在 → missing-tool error (死登记, 2026-09-28 清出 25 条)."""
    _write(tmp_path / "scripts" / "check-real.py", "print('ok')\n")
    _write(
        tmp_path / "ci-surfaces.yaml",
        "version: 1\nsurfaces:\n"
        "  - id: real\n    tool: scripts/check-real.py\n    workflow: (none)\n    status: active\n"
        "  - id: gone\n    tool: scripts/check-gone.py\n    workflow: (none)\n    status: orphan\n",
    )
    report = cs.check_ci_surfaces()
    missing = [e for e in report["errors"] if e.startswith("missing-tool")]
    assert len(missing) == 1 and "scripts/check-gone.py" in missing[0]


# ── 2026-09-29: `_discover_wiring` 的跨行贪婪回归 ─────────────────────────────
# 旧式 `uv run[^|]*` 的 `[^|]` **会匹配换行**且贪婪 ⇒ 一处 `uv run pytest src/...`
# 吞掉其后所有 step 的 `bin/*.py`(只捕获最后一个) ⇒ unregistered-check 长期失明。
# 注: `[^|\n]*` 只作用于 `uv run` 那一支; 单行 `python3 bin/x.py` 由第三条备选整体匹配。


def test_cross_line_uv_run_does_not_hide_later_steps(cs) -> None:
    """回归: 更早的 `uv run ...` 不得吞掉**后续 step** 里的单行检查调用.

    判别性设计: 被吞的那个(`hidden`)后面**还有一个** ref(`visible`) —— 旧式贪婪会
    回溯到最后一个, 于是 `hidden` 消失; 现式同行则两者都在。
    实证对应: `gac-gate.yml` 的 `bin/gac/check-l0-constraints.py`(步骤名标注 `(required)`,
    blocking) 单行执行, 却被同文件更早的 `uv run ...` 吞掉 ⇒ 本检查器对它长期失明。
    """
    _write(
        cs.WORKFLOWS_DIR / "w.yml",
        "jobs:\n"
        "  j:\n"
        "    steps:\n"
        "      - run: uv run --with pytest pytest src/tests -q\n"
        "      - run: python3 bin/gac/hidden.py\n"
        "      - run: python3 bin/gac/visible.py\n",
    )

    wiring = cs._discover_wiring()

    assert {"bin/gac/hidden.py", "bin/gac/visible.py"} <= set(wiring), sorted(wiring)


def test_wired_regex_is_a_single_line_predicate() -> None:
    """白盒判别性断言: 同一段文本, 旧式跨行正则会匹配、现式不匹配; 并含两支正控制.

    `uv run pytest x` 换行后跟一个**没有解释器前缀**的路径(折叠块的典型形态),
    不属于「执行该工具」。正控制覆盖 `python3 <path>` 与 `uv run ... python <path>` 两支。
    """
    mod = _load(ROOT / "bin" / "gac" / "check-ci-surfaces.py", "check_ci_surfaces_regex")

    assert mod.WIRED_COMMAND_RE.search("uv run pytest x\n  bin/gac/y.py") is None
    assert mod.WIRED_COMMAND_RE.search("python3 bin/gac/y.py") is not None
    assert mod.WIRED_COMMAND_RE.search("uv run --with pyyaml python bin/gac/y.py") is not None
    # `uv run` 备选的独立价值: 不经 `python` 而直接跑脚本 (`uv run --with x bin/tool.py`)
    assert mod.WIRED_COMMAND_RE.search("uv run --with x bin/gac/y.py") is not None
    assert mod.WIRED_COMMAND_RE.search("bash bin/ssot/y.sh --json") is not None


def test_uv_run_picks_the_tool_adjacent_to_the_interpreter(cs) -> None:
    """`uv run ... python <tool> <arg>` 要取**紧邻解释器**的那个路径 (非贪婪).

    取行内最后一个(贪婪)会把**参数**误认成被执行的检查。
    """
    _write(
        cs.WORKFLOWS_DIR / "w.yml",
        "jobs:\n  j:\n    steps:\n      - run: uv run --with x python bin/gac/tool.py bin/gac/arg.py\n",
    )

    wiring = cs._discover_wiring()

    assert "bin/gac/tool.py" in wiring, sorted(wiring)


def test_folded_argument_list_is_not_treated_as_executed(cs) -> None:
    """`run: >-` 折叠块里逐行的文件列表是**参数**(如 ruff 的 lint 目标), 不是执行.

    否则 `uv run --with ruff ruff check` + 一串 `bin/*.py` 会产出 9 条假的
    unregistered-check (2026-09-29 实测: 取消同行约束后 error 11 条, 其中 9 条为假阳)。
    """
    _write(
        cs.WORKFLOWS_DIR / "w.yml",
        "jobs:\n  j:\n    steps:\n"
        "      - run: >-\n"
        "          uv run --with ruff ruff check\n"
        "          bin/gac/linted-only.py\n",
    )

    wiring = cs._discover_wiring()

    assert "bin/gac/linted-only.py" not in wiring, sorted(wiring)


def test_required_l0_check_is_discovered_and_registered() -> None:
    """具体回归锚: gac-gate 里那个 required 的 L0 检查必须可见且已登记."""
    import yaml

    mod = _load(ROOT / "bin" / "gac" / "check-ci-surfaces.py", "check_ci_surfaces_l0")
    l0 = "bin/gac/check-l0-constraints.py"

    wiring = mod._discover_wiring()
    assert l0 in wiring, sorted(wiring)
    assert "gac-gate.yml" in wiring[l0]["workflows"]

    payload = yaml.safe_load(
        (ROOT / ".omo/_truth/registry/ci-surfaces.yaml").read_text(encoding="utf-8")
    )
    assert l0 in {str(s.get("tool")) for s in payload["surfaces"]}
