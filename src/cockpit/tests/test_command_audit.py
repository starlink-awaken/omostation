"""command-audit 体系测试: 树枚举 / init 一致性 / schema 校验 / lint 过期 / create_parser 回归。"""

from __future__ import annotations

import datetime
import importlib

import pytest
import yaml

from cockpit.commands import command_audit as ca


@pytest.fixture(scope="module")
def nodes():
    return ca.walk_command_tree()


def test_walk_tree_has_expected_shape(nodes):
    assert len(nodes) > 300, f"预期 300+ 节点, 实得 {len(nodes)}"
    tops = {n.split(".")[0] for n in nodes}
    for expected in ["research", "memory", "gac", "bos", "command-audit"]:
        assert expected in tops, f"缺少顶级命令 {expected}"
    assert "research.list" in nodes
    assert len(nodes) == len(set(nodes)), "存在重复节点"


def test_init_generates_file_per_node(tmp_path, nodes, monkeypatch):
    monkeypatch.setattr(ca, "AUDIT_DIR", tmp_path)
    created = 0
    for n in nodes:
        p = ca.card_path(n)
        if not p.exists():
            ca.dump_card(ca.skeleton(n), p)
            created += 1
    assert created == len(nodes)
    have, missing = ca.coverage(nodes)
    assert len(have) == len(nodes) and not missing


def _write_card(path, cmd_path, *, score=None, evidence="", total=None, drop=None, last_audited=None):
    data = ca.skeleton(cmd_path)
    for k in list(data["dimensions"]):
        if drop and k in drop:
            del data["dimensions"][k]
    if score is not None:
        data["dimensions"]["functionality"] = {"score": score, "evidence": evidence, "suggestion": ""}
    if total is not None:
        data["summary"]["total"] = total
    if last_audited:
        data["meta"]["last_audited"] = last_audited
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False))
    return data


def test_validate_catches_bad_score(tmp_path):
    d = _write_card(tmp_path / "x.yaml", "x", score=7)
    errs = ca.validate_card(d, "x")
    assert any("score 非法" in e for e in errs)


def test_validate_catches_missing_evidence(tmp_path):
    d = _write_card(tmp_path / "x.yaml", "x", score=4, evidence="  ")
    errs = ca.validate_card(d, "x")
    assert any("evidence 必填" in e for e in errs)


def test_validate_catches_missing_dimension(tmp_path):
    d = _write_card(tmp_path / "x.yaml", "x", drop={"stability"})
    errs = ca.validate_card(d, "x")
    assert any("缺失维度" in e for e in errs)


def test_validate_rejects_handwritten_total(tmp_path):
    d = _write_card(tmp_path / "x.yaml", "x", total=4.2)
    errs = ca.validate_card(d, "x")
    assert any("手写" in e for e in errs)


def test_validate_ok_on_skeleton(tmp_path):
    d = _write_card(tmp_path / "x.yaml", "x")
    assert ca.validate_card(d, "x") == []


def test_lint_coverage_and_staleness(tmp_path, monkeypatch):
    monkeypatch.setattr(ca, "AUDIT_DIR", tmp_path)
    # 覆盖不全: 只写一张
    _write_card(ca.card_path("x", tmp_path), "x", score=4, evidence="e", last_audited="2026-08-01")
    nodes = ["x", "y"]
    have, missing = ca.coverage(nodes, tmp_path)
    assert have == ["x"] and missing == ["y"]
    # 新鲜卡不过期
    data = ca.load_card(ca.card_path("x", tmp_path))
    assert not ca.is_stale(data, today=datetime.date(2026, 8, 15))
    # 超 180 天过期
    assert ca.is_stale(data, today=datetime.date(2027, 3, 1))
    # 未评审 (无 score) 的骨架即使无 last_audited 也不触发过期 lint 分支
    fresh = ca.skeleton("z")
    assert all(d["score"] is None for d in fresh["dimensions"].values())


def test_grade_and_total():
    assert ca.grade_of(None) == "-"
    assert ca.grade_of(4.8) == "S"
    assert ca.grade_of(4.0) == "A"
    assert ca.grade_of(3.0) == "B"
    assert ca.grade_of(2.0) == "C"
    assert ca.grade_of(1.0) == "D"
    d = {"dimensions": {k: {"score": 4} for k in ca.DIMENSIONS}}
    assert ca.compute_total(d) == 4.0
    assert ca.compute_total(ca.skeleton("x")) is None


def test_create_parser_extracted_main_regression():
    """create_parser() 抽取后 cli.main 仍可构建并分派 (零回归冒烟)."""
    cli = importlib.import_module("cockpit.cli")
    parser, sub, cls = cli.create_parser()
    assert parser.prog == "cockpit"
    assert hasattr(cli, "main")
    top_cmds = set(sub.choices)
    for expected in ["research", "memory", "gac", "command-audit"]:
        assert expected in top_cmds
