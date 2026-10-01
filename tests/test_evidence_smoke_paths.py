from __future__ import annotations

import importlib.util
from pathlib import Path

STATE_ROOT_ENV = "OMOSTATION_STATE_ROOT"


def _load(module_name: str, relative_path: str):
    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location(module_name, root / relative_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_evidence_smoke():
    return _load("evidence_smoke_under_test", "bin/gac/evidence-smoke.py")


def _load_task_inventory():
    return _load("task_inventory_under_test", "bin/gac/task-inventory.py")


def test_stdio_script_is_resolved_relative_to_declared_directory(tmp_path, monkeypatch):
    module = _load_evidence_smoke()
    monkeypatch.setattr(module, "WORKSPACE", tmp_path)
    script = tmp_path / "projects/omlxc/examples/live.py"
    script.parent.mkdir(parents=True)
    script.write_text("print('ok')\n", encoding="utf-8")

    ok, reason = module._check_stdio(
        ["uv", "run", "--directory", "projects/omlxc", "python", "examples/live.py"]
    )

    assert (ok, reason) == (True, "ok (script)")


def test_stdio_missing_script_fails_closed_below_declared_directory(tmp_path, monkeypatch):
    module = _load_evidence_smoke()
    monkeypatch.setattr(module, "WORKSPACE", tmp_path)
    (tmp_path / "projects/omlxc").mkdir(parents=True)

    ok, reason = module._check_stdio(
        ["uv", "run", "--directory", "projects/omlxc", "python", "examples/missing.py"]
    )

    assert ok is False
    assert reason == "script not found: examples/missing.py"


def test_stdio_script_without_directory_remains_workspace_relative(tmp_path, monkeypatch):
    module = _load_evidence_smoke()
    monkeypatch.setattr(module, "WORKSPACE", tmp_path)
    script = tmp_path / "scripts/live.py"
    script.parent.mkdir(parents=True)
    script.write_text("print('ok')\n", encoding="utf-8")

    ok, reason = module._check_stdio(["python", "scripts/live.py"])

    assert (ok, reason) == (True, "ok (script)")


# ── ADR-0456 C6: system.yaml 的写目标跟随 profile，不写宿主检出 ──────────────


def test_declared_profile_moves_health_score_evidence_write_off_the_checkout(tmp_path, monkeypatch):
    import yaml

    module = _load_evidence_smoke()
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    state_root = tmp_path / "state"
    (state_root / ".omo" / "state").mkdir(parents=True)
    state_yaml = state_root / ".omo" / "state" / "system.yaml"
    state_yaml.write_text("health_score: 91\n", encoding="utf-8")
    monkeypatch.setenv(STATE_ROOT_ENV, str(state_root))

    ok, msg = module._write_health_score_evidence(91.0)

    assert ok is True, msg
    assert module._system_yaml() == state_yaml
    data = yaml.safe_load(state_yaml.read_text(encoding="utf-8"))
    assert data["health_score_evidence"] == 91.0
    assert data["health_score_evidence_source"] == "bin/gac/evidence-smoke.py"
    # 写面闭合的判据不是「看起来对了」，而是它确实不在检出里 (否则 sync 一次就脏 git status)
    assert module.WORKSPACE not in module._system_yaml().parents


def test_undeclared_profile_keeps_the_legacy_system_yaml_path_string(tmp_path, monkeypatch):
    module = _load_evidence_smoke()
    monkeypatch.delenv(STATE_ROOT_ENV, raising=False)

    assert str(module._system_yaml()) == str(module.WORKSPACE / ".omo" / "state" / "system.yaml")


# ── ADR-0456 B5 残留: bin/ 侧其余写手 (evidence-smoke OUTPUT_DIR / task-inventory 产物) ──
# 判据形状同上：写面跟 profile，读面只有写者已翻根时才跟着翻 —— 所以每一对断言都是
# 「这个常量移了 + 那个常量没移」，只测其一都能被半改骗过去。


def test_declared_profile_moves_evidence_smoke_output_dir_off_the_checkout(tmp_path, monkeypatch):
    state_root = tmp_path / "state"
    monkeypatch.setenv(STATE_ROOT_ENV, str(state_root))
    module = _load_evidence_smoke()

    assert module.OUTPUT_DIR == state_root / ".omo" / "_delivery" / "evidence-smoke"
    assert module.WORKSPACE not in module.OUTPUT_DIR.parents


def test_evidence_smoke_jsonl_logs_stay_on_the_checkout(tmp_path, monkeypatch):
    """GOV_LOG / EVENTS_LOG 被 git 跟踪且有 15+ 检出侧读者，只翻写者会让读者读旧数据。"""
    state_root = tmp_path / "state"
    monkeypatch.setenv(STATE_ROOT_ENV, str(state_root))
    module = _load_evidence_smoke()

    assert module.GOV_LOG == module.WORKSPACE / ".omo" / "_knowledge" / "governance-history.jsonl"
    assert module.EVENTS_LOG == module.WORKSPACE / ".omo" / "_knowledge" / "omo-events.jsonl"


def test_declared_profile_moves_task_inventory_artifacts_off_the_checkout(tmp_path, monkeypatch):
    state_root = tmp_path / "state"
    monkeypatch.setenv(STATE_ROOT_ENV, str(state_root))
    module = _load_task_inventory()

    assert module.SNAP_DIR == state_root / "runtime" / "task-inventory" / "snapshots"
    assert module.DRIFTS == state_root / "runtime" / "task-inventory" / "drifts.jsonl"
    # REGISTRY 没有可追的写者，panorama-collect.py:3198 又读同一个文件 ⇒ 保持检出侧
    assert module.REGISTRY == module.WORKSPACE / ".omo" / "state" / "task-registry.yaml"


def test_undeclared_profile_keeps_legacy_root_side_writer_paths(tmp_path, monkeypatch):
    """未声明 profile 时路径字符串逐字节等于改前 —— 本轮对今天的运行态无效应。"""
    monkeypatch.delenv(STATE_ROOT_ENV, raising=False)
    smoke = _load_evidence_smoke()
    inventory = _load_task_inventory()

    assert str(smoke.OUTPUT_DIR) == str(smoke.WORKSPACE / ".omo" / "_delivery" / "evidence-smoke")
    assert str(inventory.SNAP_DIR) == str(inventory.WORKSPACE / "runtime" / "task-inventory" / "snapshots")
    assert str(inventory.DRIFTS) == str(inventory.WORKSPACE / "runtime" / "task-inventory" / "drifts.jsonl")
