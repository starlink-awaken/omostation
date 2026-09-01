"""chain runner 单元测试 — dry-run / 状态机 / resume / HITL (注入 fake executor, 不真调命令)."""

import json

import pytest

from cockpit.chain.runner import parse_params, run_chain
from cockpit.chain.spec import parse_spec


def _spec(steps, hitl=None, on_chain_failure="abort", params=None):
    return parse_spec(
        {
            "id": "t",
            "name": "test",
            "timeout": 30,
            "on_chain_failure": on_chain_failure,
            "params": params or {},
            "steps": steps,
            "hitl": hitl or [],
        }
    )


class FakeExec:
    """按命令名脚本化返回结果的 fake executor."""

    def __init__(self, script: dict, record: list | None = None):
        self.script = script
        self.record = record if record is not None else []

    def __call__(self, argv, timeout, env):
        self.record.append(argv)
        return self.script.get(argv[0], {"exit_code": 0, "stdout": "", "stderr": ""})


_RUNS_TARGET: list = [None]


@pytest.fixture(autouse=True)
def _runs_dir(tmp_path, monkeypatch):
    import cockpit.chain.runner as runner_mod

    _RUNS_TARGET[0] = tmp_path / "chain-runs"
    monkeypatch.setattr(runner_mod, "runs_dir", lambda: _RUNS_TARGET[0])


def test_dry_run_no_exec_no_state(capsys):
    calls: list = []
    spec = _spec([{"name": "a", "command": "cockpit status", "args": ["--json"]}])
    rc = run_chain(spec, dry_run=True, exec_cmd=FakeExec({}, calls))
    assert rc == 0
    assert calls == []  # 不执行
    assert not list(_RUNS_TARGET[0].glob("*/state.json"))
    out = capsys.readouterr().out
    assert "dry-run" in out


def test_all_success():
    spec = _spec([{"name": "a", "command": "cockpit status"}, {"name": "b", "command": "cockpit health"}])
    rc = run_chain(spec, exec_cmd=FakeExec({"status": {"exit_code": 0, "stdout": "ok", "stderr": ""}}))
    assert rc == 0


def test_skip_on_when_false():
    spec = _spec(
        [
            {"name": "a", "command": "cockpit health", "args": ["--json"], "capture_output_to": "h"},
            {"name": "b", "command": "cockpit im-triage", "when": "steps.a.json.status == 'degraded'"},
            {"name": "c", "command": "cockpit ops", "when": "steps.a.json.status != 'degraded'"},
        ]
    )
    exec = FakeExec({"health": {"exit_code": 0, "stdout": json.dumps({"status": "healthy"}), "stderr": ""}})
    rc = run_chain(spec, exec_cmd=exec)
    assert rc == 0
    state_files = list(_RUNS_TARGET[0].glob("*/state.json"))
    assert len(state_files) == 1
    state = json.loads(state_files[0].read_text())
    assert state["steps_state"]["b"]["status"] == "skipped"
    assert state["steps_state"]["c"]["status"] == "succeeded"
    assert state["status"] == "succeeded"


def test_abort_on_failure():
    spec = _spec(
        [
            {"name": "a", "command": "cockpit status"},
            {"name": "b", "command": "cockpit health"},
        ]
    )
    calls: list = []
    rc = run_chain(spec, exec_cmd=FakeExec({"status": {"exit_code": 3, "stdout": "", "stderr": "err"}}, calls))
    assert rc == 3
    assert len(calls) == 1  # health 未执行
    state = json.loads(list(_RUNS_TARGET[0].glob("*/state.json"))[0].read_text())
    assert state["status"] == "aborted"


def test_continue_on_failure():
    spec = _spec(
        [
            {"name": "a", "command": "cockpit status", "on_failure": "continue"},
            {"name": "b", "command": "cockpit health"},
        ]
    )
    calls: list = []
    rc = run_chain(spec, exec_cmd=FakeExec({"status": {"exit_code": 3, "stdout": "", "stderr": "err"}}, calls))
    assert len(calls) == 2  # health 仍执行
    assert rc == 3  # continue 的失败保留最终 rc


def test_retry_until_success(monkeypatch):
    monkeypatch.setattr("cockpit.chain.runner.time.sleep", lambda s: None)
    spec = _spec([{"name": "a", "command": "cockpit status", "retry": {"max": 2, "backoff": 0}}])
    attempts = {"n": 0}

    def flaky(argv, timeout, env):
        attempts["n"] += 1
        return {"exit_code": 0 if attempts["n"] >= 2 else 1, "stdout": "", "stderr": ""}

    rc = run_chain(spec, exec_cmd=flaky)
    assert rc == 0
    assert attempts["n"] == 2
    state = json.loads(list(_RUNS_TARGET[0].glob("*/state.json"))[0].read_text())
    assert state["steps_state"]["a"]["attempts"] == 2


def test_retry_exhausted_aborts(monkeypatch):
    monkeypatch.setattr("cockpit.chain.runner.time.sleep", lambda s: None)
    spec = _spec([{"name": "a", "command": "cockpit status", "retry": {"max": 1, "backoff": 0}}])
    rc = run_chain(spec, exec_cmd=FakeExec({"status": {"exit_code": 5, "stdout": "", "stderr": "x"}}))
    assert rc == 5
    state = json.loads(list(_RUNS_TARGET[0].glob("*/state.json"))[0].read_text())
    assert state["steps_state"]["a"]["attempts"] == 2


def test_resume_skips_succeeded():
    spec = _spec([{"name": "a", "command": "cockpit status"}, {"name": "b", "command": "cockpit health", "on_failure": "continue"}])
    calls: list = []
    rc1 = run_chain(spec, exec_cmd=FakeExec({"status": {"exit_code": 0, "stdout": "", "stderr": ""}}, calls))
    state1 = json.loads(list(_RUNS_TARGET[0].glob("*/state.json"))[0].read_text())
    # 用第一个 run_id resume (后续全成功)
    run_chain(spec, resume_run_id=state1["run_id"], exec_cmd=FakeExec({}, calls))
    assert rc1 == 0
    # resume 后 [a] 不再执行: calls 总数 = 第1轮2次 + resume 0 次(全部succeeded)
    assert len(calls) == 2


def test_resume_missing_run():
    spec = _spec([{"name": "a", "command": "cockpit status"}])
    rc = run_chain(spec, resume_run_id="chain-nope-0000", exec_cmd=FakeExec({}))
    assert rc == 2


def test_hitl_non_interactive_continues(capsys):
    spec = _spec(
        [{"name": "a", "command": "cockpit status"}],
        hitl=[{"at": "a", "prompt": "确认?", "on_timeout": "abort"}],
    )
    calls: list = []
    rc = run_chain(spec, non_interactive=True, exec_cmd=FakeExec({}, calls))
    assert rc == 0
    assert len(calls) == 1
    assert "默认继续" in capsys.readouterr().out


def test_hitl_interactive_abort(monkeypatch):
    spec = _spec(
        [{"name": "a", "command": "cockpit status"}],
        hitl=[{"at": "a", "prompt": "确认?", "on_timeout": "abort"}],
    )
    answers = iter(["n"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))
    calls: list = []
    rc = run_chain(spec, non_interactive=False, exec_cmd=FakeExec({}, calls))
    assert rc == 1
    assert calls == []
    state = json.loads(list(_RUNS_TARGET[0].glob("*/state.json"))[0].read_text())
    assert state["status"] == "aborted"


def test_template_param_passthrough():
    spec = _spec(
        [{"name": "a", "command": "cockpit research", "args": ["create", "{{params.topic}}"]}],
        params={"topic": {"type": "str", "default": "dflt"}},
    )
    calls: list = []
    rc = run_chain(spec, exec_cmd=FakeExec({}, calls))
    assert rc == 0
    assert calls[0] == ["research", "create", "dflt"]


def test_parse_params():
    assert parse_params(["a=1", "b=x=y"]) == {"a": "1", "b": "x=y"}
    with pytest.raises(ValueError):
        parse_params(["novalue"])
