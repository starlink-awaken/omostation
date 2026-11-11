#!/usr/bin/env python3
"""gac-bootstrap 层3/层4/层6 的仪器自证钉 (BET-Y2Q4-T10-347).

三组变异各钉一处, 缺一处就红:
  1. 层3 glob 退回 `bin/gac-*.py` 单目录 → 分母归零 → 零分母必须判红 (不是判绿)
  2. 层4 存在性判据退回 `source_type == indexed` 早退 → 非 indexed 的路径型登记不再被看
  3. 层6 平面比对换成文本正则 (扫 gac-local-gate.py 源码) → DEFAULT_POLICY 里的字面量
     被当成"已接线", 两个执行平面缺席者从点名清单里消失 = 假绿
"""

from __future__ import annotations

import importlib.util
import json
import pathlib
import re

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[2]
BOOT_PATH = ROOT / "bin" / "gac" / "gac-bootstrap.py"

# 本 BET 立案的两个人证: 登记面写 workflow=gac-gate.yml + triggers=[gac_local_gate, per_pr],
# 但 runtime GATES_LIST / CI run: / hooks / sgf-policy 四处都没有它们.
UNREACHED = {
    "bin/gac/check-gate-detail-contract.py",
    "bin/gac/check-cron-interpreter-executability.py",
}


def _boot():
    spec = importlib.util.spec_from_file_location("gac_bootstrap_under_test", BOOT_PATH)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------- 层3


def test_l3_census_is_a_real_population_not_zero() -> None:
    b = _boot()
    assert len(b.GAC_TOOLS) > 300, "层3 普查分母跌回 300 以下: glob 又只看一个目录了"
    r = b.check_tools_alive()
    assert r["total"] == len(b.GAC_TOOLS) > 300
    assert r["audited"] == r["total"]
    assert not r["instrument_dead"]
    assert (ROOT / "bin" / "gac" / "gac-bootstrap.py") in b.GAC_TOOLS


def test_l3_zero_denominator_fails_instead_of_passing() -> None:
    b = _boot()
    b.GAC_TOOLS = []  # 变异: 退回 bin/gac-*.py 单目录, 324 个真工具一个也看不见
    r = b.check_tools_alive()
    assert r["total"] == 0
    assert r["instrument_dead"] is True
    assert r["dead"], "零分母必须留下一条点名, 不能空名单当通过"
    assert b.run_bootstrap(as_json=True) == 1, "仪器没接上却返回 0 = 假绿"


def test_l3_dead_tool_is_named_not_silenced(tmp_path: pathlib.Path) -> None:
    b = _boot()
    ghost = tmp_path / "no_main_entry.py"
    ghost.write_text("#!/usr/bin/env python3\nprint('library-ish')\n", encoding="utf-8")
    b.GAC_TOOLS = [BOOT_PATH, ghost]
    r = b.check_tools_alive()
    assert any("no_main_entry.py" in d for d in r["dead"])
    assert r["alive"] == 1 and r["total"] == 2


# ---------------------------------------------------------------- 层4


def test_l4_covers_non_indexed_path_refs() -> None:
    b = _boot()
    fake = [
        {"id": "CR-FAKE-NATIVE", "source_type": "native", "source_ref": "bin/gac/__no_such__.py"},
        {"id": "CR-FAKE-INDEXED", "source_type": "indexed", "source_ref": "bin/gac/__gone__.py::frag"},
        {"id": "CR-FAKE-ANCHOR", "source_type": "native", "source_ref": "README.md#some-section"},
        {"id": "CR-FAKE-NONPATH", "source_type": "native", "source_ref": "gac.schema.executor_enum"},
    ]
    b.load_rules = lambda: fake
    r = b.check_indexed_integrity()
    # 旧口径 (只走 indexed) 在这里 checked=1 / missing=1; 新口径覆盖全部路径型
    assert r["checked"] == 3, "路径型 source_ref 未被全量取到"
    assert r["missing_count"] == 2
    assert r["indexed_missing_count"] == 1, "indexed 子集必须单独可判 (始终阻断)"
    assert {m["id"] for m in r["missing"]} == {"CR-FAKE-NATIVE", "CR-FAKE-INDEXED"}
    assert "README.md" not in json.dumps(r["missing"], ensure_ascii=False)


def test_l4_god_module_refs_now_point_at_the_real_file() -> None:
    b = _boot()
    r = b.check_indexed_integrity()
    assert not any(m["missing_ref"] == "bin/gac/check-god-module.py" for m in r["missing"]), (
        "CR-X1-GOD-MODULE-LIMIT / CR-X2-GOD-MODULE-EDIT 的 source_ref 又指回不存在的 bin/gac/ 目录"
    )
    assert (ROOT / "bin" / "ssot" / "check-god-module.py").is_file()
    for rule in b.load_rules():
        if rule.get("id") in {"CR-X1-GOD-MODULE-LIMIT", "CR-X2-GOD-MODULE-EDIT"}:
            assert rule["source_ref"] == "bin/ssot/check-god-module.py"


def test_l4_uninitialized_submodule_is_device_unavailable_not_pass() -> None:
    b = _boot()
    b.load_rules = lambda: [{"id": "CR-FAKE-SUB", "source_type": "native", "source_ref": "projects/__nosuch__/x.yaml"}]
    r = b.check_indexed_integrity()
    assert r["checked"] == 1
    assert r["missing_count"] == 0
    assert [d["id"] for d in r["device_unavailable"]] == ["CR-FAKE-SUB"], (
        "子模块未检出必须显式标注装置不可用, 不能静默计入通过"
    )


# ---------------------------------------------------------------- 层6


def _synthetic_planes(b, tmp: pathlib.Path, runtime_tokens: set[str]) -> None:
    """把登记面/平面都换成 tmp 合成物, 让层6 判定可复现 (不吃宿主 CI 状态)."""
    surfaces = tmp / "ci-surfaces.yaml"
    surfaces.write_text(
        yaml.safe_dump(
            {
                "surfaces": [
                    {
                        "id": "s-ghost",
                        "tool": "bin/gac/ghost.py",
                        "workflow": "gac-gate.yml",
                        "gate": False,
                        "triggers": ["gac_local_gate", "per_pr"],
                        "status": "active",
                    },
                    {
                        "id": "s-real",
                        "tool": "bin/gac/real.py",
                        "workflow": "gac-gate.yml",
                        "gate": False,
                        "triggers": ["gac_local_gate"],
                        "status": "active",
                    },
                    {
                        "id": "s-manual",
                        "tool": "bin/gac/manual-only.py",
                        "workflow": "(none)",
                        "gate": False,
                        "triggers": ["manual"],
                        "status": "active",
                    },
                    {
                        "id": "s-gateonly",
                        "tool": "bin/gac/gate-flag-no-plane.py",
                        "workflow": "(none)",
                        "gate": True,
                        "triggers": [],
                        "status": "active",
                    },
                    {
                        "id": "s-runner",
                        "tool": "bin/gac/runner-only.py",
                        "workflow": "runner.yml",
                        "gate": False,
                        "triggers": ["per_pr"],
                        "status": "active",
                    },
                    {"id": "s-retired", "tool": "bin/gac/retired.py", "gate": True, "status": "retired"},
                ]
            },
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    wf = tmp / "workflows"
    wf.mkdir()
    (wf / "gac-gate.yml").write_text(
        "jobs:\n  gate:\n    steps:\n      - run: python3 bin/gac/real.py --json\n"
        "      - with:\n          body: '失败请跑 python3 bin/gac/ghost.py'\n        run: echo skip\n",
        encoding="utf-8",
    )
    hooks = tmp / "hooks"
    hooks.mkdir()
    (hooks / "pre-commit").write_text('#!/bin/sh\npython3 "$ROOT/bin/gac/hooked.py"\n', encoding="utf-8")
    # registry-driven 承接面: runner.yml 自己不点名任何工具, 靠 ci-check-runner --workflow 读登记
    (wf / "runner.yml").write_text(
        "jobs:\n  r:\n    steps:\n      - run: python3 bin/gac/ci-check-runner.py --workflow runner.yml\n",
        encoding="utf-8",
    )
    b.CI_SURFACES = surfaces
    b.WORKFLOWS_DIR = wf
    b.HOOKS_DIR = hooks
    b._runtime_plane = lambda: (runtime_tokens, 1, "sgf", {})


def test_l6_names_declared_but_unexecuted(tmp_path: pathlib.Path) -> None:
    b = _boot()
    _synthetic_planes(b, tmp_path, {"bin/gac/real.py"})
    r = b.check_plane_coverage()
    named = {v["tool"]: v for v in r["violations"]}
    assert "bin/gac/ghost.py" in named, "声称 gac_local_gate 却四平面全缺席, 必须点名"
    assert "bin/gac/gate-flag-no-plane.py" in named, "gate=true 但无任何平面声明也该点名"
    assert named["bin/gac/gate-flag-no-plane.py"]["reason"].startswith("声明 gate=true")
    assert "bin/gac/real.py" not in named
    assert "bin/gac/runner-only.py" not in named, "ci-check-runner --workflow 承接面命中, 不该被当成谎报"
    assert "bin/gac/manual-only.py" not in named, "只声明 manual 的工具不该被当成谎报"
    assert "bin/gac/retired.py" not in named
    assert r["declared"] == 4 and r["reached"] == 2 and r["manual_exempt"] == 1
    assert r["planes"]["ci"]["runner_covered"] == ["runner.yml"]
    assert r["ok"] is False


def test_l6_run_position_is_what_counts(tmp_path: pathlib.Path) -> None:
    """同一个字面量, 出现在 run: 里算接线, 出现在 with.body 文案里不算 (结构口径)."""
    b = _boot()
    _synthetic_planes(b, tmp_path, set())
    doc = yaml.safe_load((b.WORKFLOWS_DIR / "gac-gate.yml").read_text(encoding="utf-8"))
    bodies = " ".join(b._collect_run_bodies(doc))
    assert "bin/gac/real.py" in bodies
    assert "bin/gac/ghost.py" not in bodies, "文案里的路径不能被判成已接线"


def test_l6_text_regex_mutation_would_go_green() -> None:
    """变异钉: 把平面比对换成"扫源码文本", 真缺席者就从点名清单消失 —— 证明本层价值.

    红条数记在这里: 真数据下结构口径点名这两条 (DEFAULT_POLICY 的字面量不算接线),
    换成正则口径后两条同时消失 = 假绿.
    """
    b = _boot()
    src = (BOOT_PATH.parent / "gac-local-gate.py").read_text(encoding="utf-8")
    regex_tokens = set(re.findall(r"[\w./$-]+\.py", src))
    assert UNREACHED <= regex_tokens, "前提不成立: 两个字面量已不在 gac-local-gate.py 里"

    named = {v["tool"] for v in b.check_plane_coverage()["violations"]}
    assert UNREACHED <= named, "结构口径必须点名这两个执行平面缺席者"

    b._runtime_plane = lambda: (regex_tokens, 90, "sgf", {})
    mutated = {v["tool"] for v in b.check_plane_coverage()["violations"]}
    assert not (UNREACHED <= mutated), "文本正则口径把它们当成已接线 —— 正是本层要防的假绿"


def test_l6_real_population_is_measured_with_denominators() -> None:
    b = _boot()
    r = b.check_plane_coverage()
    assert r["available"] is True
    assert r["declared"] > 100, "登记面读数跌回 100 以下 = 仪器没接上"
    assert not r.get("instrument_dead")
    assert r["planes"]["runtime"]["policy_source"] == "sgf", (
        "runtime 平面读的是 DEFAULT_POLICY 降级副本, 不是 sgf-policy 执行面"
    )
    assert r["reached"] + len(r["violations"]) == r["declared"]
    for v in r["violations"]:
        assert v["tool"].endswith(".py")
        if v.get("verdict") == "declared_no_execution_plane":
            assert "四平面全缺席" in v["reason"]
        else:
            assert v.get("verdict") == "device_unavailable", f"未预期的判定: {v}"


# ---------------------------------------------------------------- 总体口径


def test_advisory_switch_is_read_from_the_registry_rule() -> None:
    b = _boot()
    blocking, review_before = b.self_enforcement()
    rule = next(r for r in b.load_rules() if r.get("id") == "CR-X2-GAC-BOOTSTRAP")
    assert blocking is (rule.get("enforcement") == "blocking")
    assert review_before == str(rule.get("review_before", ""))
    assert review_before, "review_before 必须可解析, 否则限期收敛没有期限"


def test_bootstrap_json_contract_keys_stay_for_healthcheck() -> None:
    """gac-healthcheck.py:288-294 按固定 key 取值, 改名就是打断另一个平面."""
    b = _boot()
    report = {
        "tools": b.check_tools_alive(),
        "indexed_integrity": b.check_indexed_integrity(),
        "exec_effective": b.check_exec_effective(),
        "schema_self": b.check_schema_self_consistent(),
    }
    for key, field in (
        ("tools", "alive"),
        ("tools", "total"),
        ("indexed_integrity", "missing_count"),
        ("exec_effective", "issues_count"),
        ("schema_self", "issues_count"),
    ):
        assert field in report[key], f"gac-healthcheck 依赖的 {key}.{field} 不见了"
