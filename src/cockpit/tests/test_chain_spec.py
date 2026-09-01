"""chain spec / context 单元测试 — schema 校验 / 搜索路径 / 模板 / 条件求值."""

import pytest

from cockpit.chain.context import (
    ChainConditionError,
    ChainTemplateError,
    evaluate_condition,
    render_template,
)
from cockpit.chain.spec import ChainSpecError, parse_spec, validate_command_catalog, validate_spec


def _raw(**kw):
    base = {
        "id": "t",
        "name": "test chain",
        "steps": [{"name": "s1", "command": "cockpit status"}],
    }
    base.update(kw)
    return base


# ── schema 校验 ──────────────────────────────────────────────────────────────


def test_validate_ok():
    assert validate_spec(_raw()) == []


def test_validate_missing_id_name_steps():
    errors = validate_spec({"steps": []})
    assert any("id" in e for e in errors)
    assert any("name" in e for e in errors)
    assert any("steps" in e for e in errors)


def test_validate_bad_on_failure():
    errors = validate_spec(_raw(steps=[{"name": "a", "command": "x", "on_failure": "explode"}]))
    assert any("on_failure" in e for e in errors)


def test_validate_duplicate_step_names():
    errors = validate_spec(_raw(steps=[{"name": "a", "command": "x"}, {"name": "a", "command": "y"}]))
    assert any("重复" in e for e in errors)


def test_validate_hitl_unknown_step():
    errors = validate_spec(_raw(hitl=[{"at": "nope", "prompt": "?", "on_timeout": "abort"}]))
    assert any("hitl" in e for e in errors)


# ── 搜索路径优先级 ───────────────────────────────────────────────────────────


def test_search_paths_priority():
    from cockpit.chain import spec as spec_mod

    paths = spec_mod.search_paths()
    assert str(spec_mod.REPO_ROOT / "config" / "chains") == str(paths[0])
    assert len(paths) == 3


def test_list_chains_includes_demos():
    from cockpit.chain.spec import list_chains

    chains = list_chains()
    for cid in ("governance-patrol", "research-production", "incident-triage", "agent-collab"):
        assert cid in chains


def test_load_chain_missing_raises():
    from cockpit.chain.spec import load_chain

    with pytest.raises(ChainSpecError):
        load_chain("no-such-chain-xyz")


# ── validate_command_catalog ─────────────────────────────────────────────────


def test_validate_command_catalog_ok():
    spec = parse_spec(_raw(steps=[{"name": "a", "command": "cockpit status"}]))
    assert validate_command_catalog(spec) == []


def test_validate_command_catalog_unknown():
    spec = parse_spec(_raw(steps=[{"name": "a", "command": "definitely-not-a-cmd"}]))
    errors = validate_command_catalog(spec)
    assert any("不在 COMMAND_CATALOG" in e for e in errors)


# ── 模板渲染 ─────────────────────────────────────────────────────────────────


def _ctx():
    return {
        "params": {"topic": "attn"},
        "env": {},
        "steps": {
            "s1": {"exit_code": 0, "stdout": '{"status": "degraded", "items": [{"id": 7}]}', "stderr": "boom"},
        },
        "prev": {"stdout": "line\n"},
    }


def test_render_params_and_env(monkeypatch):
    monkeypatch.setenv("MY_VAR", "vvv")
    ctx = _ctx()
    ctx["env"] = {"MY_VAR": "vvv"}
    assert render_template("{{params.topic}}/{{env.MY_VAR}}", ctx) == "attn/vvv"


def test_render_steps_fields():
    assert render_template("{{steps.s1.exit_code}}", _ctx()) == "0"
    assert render_template("{{steps.s1.stderr}}", _ctx()) == "boom"


def test_render_steps_json_path():
    assert render_template("{{steps.s1.json.status}}", _ctx()) == "degraded"
    assert render_template("{{steps.s1.json.items[0].id}}", _ctx()) == "7"


def test_render_steps_json_missing_path():
    with pytest.raises(ChainTemplateError, match="路径不存在"):
        render_template("{{steps.s1.json.nope}}", _ctx())


def test_render_steps_json_not_parseable():
    ctx = _ctx()
    ctx["steps"]["s2"] = {"stdout": "not json"}
    with pytest.raises(ChainTemplateError, match="不是合法 JSON"):
        render_template("{{steps.s2.json.x}}", ctx)


def test_render_unknown_ref():
    with pytest.raises(ChainTemplateError, match="未知模板引用"):
        render_template("{{bogus.x}}", _ctx())


def test_render_pending_step():
    with pytest.raises(ChainTemplateError, match="未执行的步骤"):
        render_template("{{steps.later.stdout}}", _ctx())


def test_render_prev_output():
    assert render_template("{{prev.output}}", _ctx()) == "line"


# ── 条件求值 ─────────────────────────────────────────────────────────────────


def test_condition_eq_str():
    assert evaluate_condition("params.x == 'a'", {"params": {"x": "a"}})
    assert not evaluate_condition("params.x == 'b'", {"params": {"x": "a"}})


def test_condition_ne():
    assert evaluate_condition("params.x != 'b'", {"params": {"x": "a"}})


def test_condition_numeric_compare():
    assert evaluate_condition("steps.s1.exit_code > -1", _ctx())
    assert evaluate_condition("steps.s1.exit_code <= 0", _ctx())
    assert not evaluate_condition("steps.s1.exit_code < 0", _ctx())


def test_condition_contains():
    assert evaluate_condition("steps.s1.stderr contains 'oo'", _ctx())


def test_condition_and_or_not():
    assert evaluate_condition("params.topic == 'attn' and steps.s1.exit_code == 0", _ctx())
    assert evaluate_condition("params.topic == 'zzz' or steps.s1.exit_code == 0", _ctx())
    assert evaluate_condition("not (params.topic == 'zzz')", _ctx())


def test_condition_json_field():
    ctx = _ctx()
    ctx["steps"]["s1"]["json"] = {"status": "degraded", "items": [{"id": 7}]}
    assert evaluate_condition("steps.s1.json.status == 'degraded'", ctx)
    assert evaluate_condition("steps.s1.json.items[0].id == 7", ctx)


def test_condition_parentheses():
    assert evaluate_condition("(params.topic == 'zzz' or steps.s1.exit_code == 0) and not false", _ctx())


def test_condition_empty_is_true():
    assert evaluate_condition("", {})


def test_condition_invalid_expr():
    with pytest.raises(ChainConditionError):
        evaluate_condition("params.x ===", {"params": {"x": 1}})
    with pytest.raises(ChainConditionError):
        evaluate_condition("&& ||", {})
    with pytest.raises(ChainConditionError):
        evaluate_condition("(params.x == 1", {"params": {"x": 1}})


def test_condition_unresolvable_ref():
    with pytest.raises(ChainConditionError, match="无法解析"):
        evaluate_condition("params.nope == 1", {"params": {}})
