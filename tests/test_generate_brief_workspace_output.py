from __future__ import annotations

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "bin" / "mof" / "generate-brief.py"

STATE_ROOT_ENV = "OMOSTATION_STATE_ROOT"
OUTPUT_ENV = "OMOSTATION_BRIEF_OUTPUT"


def _load(monkeypatch, *, state_root: Path | None = None, output: Path | None = None):
    if state_root is None:
        monkeypatch.delenv(STATE_ROOT_ENV, raising=False)
    else:
        monkeypatch.setenv(STATE_ROOT_ENV, str(state_root))
    if output is None:
        monkeypatch.delenv(OUTPUT_ENV, raising=False)
    else:
        monkeypatch.setenv(OUTPUT_ENV, str(output))
    spec = importlib.util.spec_from_file_location("generate_brief_test", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_explicit_output_is_used_without_dragging_the_root(monkeypatch, tmp_path: Path) -> None:
    """OMOSTATION_BRIEF_OUTPUT 只决定落盘文件名，不得把仓根一起拖走。

    改前的形状是另一个 env (OMOSTATION_WORKSPACE_ROOT) 能整根改写 —— 全仓唯一 setter 是
    crontab.new:76，而它的 cd 目标已是不存在的僵尸检出。别名删掉后这条判据仍在，
    因为「输出可指到任意处、根仍是当前检出」正是这次收敛要保证的边界。
    """
    output = tmp_path / "elsewhere" / "BRIEF.md"

    module = _load(monkeypatch, output=output)

    assert module.BRIEF_MD == output
    assert module.WORKSPACE == SCRIPT.resolve().parents[2]
    assert module.write_brief_if_changed("# generated\n") is True
    assert output.read_text(encoding="utf-8") == "# generated\n"


def test_default_output_remains_repo_root(monkeypatch) -> None:
    module = _load(monkeypatch)

    assert module.WORKSPACE == SCRIPT.resolve().parents[2]
    assert module.BRIEF_MD == SCRIPT.resolve().parents[2] / "BRIEF.md"


def test_declared_profile_moves_the_system_yaml_read_off_the_checkout(tmp_path: Path, monkeypatch) -> None:
    """system.yaml 的三个写者已全部挂 state_root ⇒ 读者必须同根，否则永远看提交的快照。"""
    state_root = tmp_path / "state"
    (state_root / ".omo" / "state").mkdir(parents=True)

    module = _load(monkeypatch, state_root=state_root)

    assert module._system_yaml() == state_root / ".omo" / "state" / "system.yaml"
    assert module.WORKSPACE not in module._system_yaml().parents
    # 反面判据：collab-dualtrack.yaml 的写者 (bin/collab/export-dualtrack.py:31) 仍是检出侧，
    # 读者不许独移 —— 把读者的检出根挪走后只在 state root 放一份，渲染必须为空。
    code_root = tmp_path / "code"
    (code_root / ".omo" / "state").mkdir(parents=True)
    monkeypatch.setattr(module, "WORKSPACE", code_root)
    (state_root / ".omo" / "state" / "collab-dualtrack.yaml").write_text(
        "capability: {scenarios: 9}\n", encoding="utf-8"
    )
    assert module._render_collab_dashboard() == []
    (code_root / ".omo" / "state" / "collab-dualtrack.yaml").write_text(
        "capability: {scenarios: 9}\n", encoding="utf-8"
    )
    assert module._render_collab_dashboard() != []


def test_undeclared_profile_keeps_the_legacy_system_yaml_path_string(monkeypatch) -> None:
    module = _load(monkeypatch)

    assert str(module._system_yaml()) == str(module.WORKSPACE / ".omo" / "state" / "system.yaml")
    # 本文件的 _load 在 exec_module **之前** setenv, 冻结常量也能绿 ⇒ 晚声明的时机判据在
    # tests/unit/test_b1_ledger_call_time.py (同一入口, 参数化覆盖)


def test_explicit_output_never_targets_documents(monkeypatch, tmp_path: Path) -> None:
    documents = tmp_path / "Documents"
    documents.mkdir()
    output = tmp_path / "Workspace" / "BRIEF.md"
    output.parent.mkdir()

    module = _load(monkeypatch, output=output)
    module.write_brief_if_changed("# Workspace brief\n")

    assert output.is_file()
    assert not (documents / "@驾驶舱" / "_control" / "BRIEF.md").exists()
